# Linux commands practice

## Topic introduction

Linux commands provide a command-line interface for interacting with the operating system and its file system. File and directory operations are among the most fundamental command-line skills because many development, administration, automation, deployment, and troubleshooting tasks depend on them.

The accompanying Python script is a self-contained practice laboratory. It progresses from basic navigation through file creation, copying, moving, deletion, searching, inspection, text processing, permissions, links, archives, pipelines, environment variables, troubleshooting, automation, and production considerations.

The demonstrations use a temporary workspace so that the practical examples do not intentionally modify the user's normal files.

The script can be run with:

    python3 linux_commands_practice.py

Linux, macOS, WSL, and other POSIX-compatible environments provide the most complete command demonstrations. On Windows without a Linux compatibility environment, the educational explanations and Python demonstrations still run, while unavailable Linux commands are skipped.

## The Linux file system

Linux organizes files and directories in a hierarchical tree.

The root directory is represented by `/`. Directories below it contain other directories and files.

Important path concepts include:

- `/` represents the root directory.
- `.` represents the current directory.
- `..` represents the parent directory.
- `~` normally represents the current user's home directory.
- An absolute path begins at `/`.
- A relative path is interpreted from the current working directory.

For example, `/home/user/documents/report.txt` is an absolute path, while `documents/report.txt` is relative.

Linux file names are case-sensitive. `report.txt`, `Report.txt`, and `REPORT.TXT` can represent three different files.

Understanding the current working directory is essential because many commands interpret relative paths from that location.

## Navigation

The primary navigation commands are `pwd`, `ls`, and `cd`.

`pwd` means print working directory. It displays the current location.

`ls` lists directory contents. Useful forms include:

    ls
    ls -l
    ls -la
    ls -lh

The `-l` option requests a long listing. It normally includes permissions, ownership, file size, timestamps, and names.

The `-a` option includes hidden entries. Linux hidden files are conventionally identified by a leading period, such as `.bashrc`.

The `-h` option commonly requests human-readable sizes.

`cd` changes the current working directory.

Typical navigation operations include:

    cd /tmp
    cd ..
    cd .
    cd ~
    cd -

The `cd -` behavior is provided by interactive shells and commonly returns to the previous working directory.

## Creating directories

`mkdir` creates directories.

A basic example is:

    mkdir project

Nested directories can be created with:

    mkdir -p project/data/raw

The `-p` option creates missing parent directories and avoids failure when an already-existing directory is part of the requested path.

The script demonstrates directory creation before performing other file operations. This reflects an important practical principle: establish and verify the intended directory structure before manipulating files inside it.

## Creating files

`touch` creates an empty file when the file does not already exist. It can also update file timestamps.

Example:

    touch notes.txt

It is important to understand that `touch` is primarily a timestamp utility rather than a dedicated content-writing command.

Text can be written from the shell using redirection. For example, `>` sends standard output to a file and replaces the previous contents, while `>>` appends to the file.

The difference is operationally significant:

    printf 'first line\n' > notes.txt
    printf 'second line\n' >> notes.txt

The first operation replaces the destination contents. The second preserves existing contents and adds new data.

Because `>` can destroy existing content, redirection should be used deliberately.

The Python script also demonstrates `pathlib.Path.write_text()`, which is often preferable when a larger Python application needs structured control over file creation and content.

## Inspecting files

Several commands are designed for inspection rather than modification.

### cat

`cat` prints file contents.

    cat notes.txt

It is convenient for small files. It is less appropriate for very large files because it attempts to send the complete content to standard output.

### less

`less` provides interactive viewing of large text files. It is generally more suitable than `cat` for logs and other large documents.

### head

`head` displays the beginning of a file.

    head -n 20 application.log

This is useful when checking file headers, configuration formats, or the first records of a dataset.

### tail

`tail` displays the end of a file.

    tail -n 50 application.log

`tail -f application.log` is commonly used to monitor a file while it is growing, particularly application and system logs.

### wc

`wc` counts lines, words, and bytes.

    wc file.txt
    wc -l file.txt
    wc -w file.txt
    wc -c file.txt

The `-l` option is useful when counting records represented by one line each.

### file

`file` attempts to identify the type of a file based on its contents and metadata rather than relying only on its extension.

    file report.txt

A file named `image.txt` can still contain binary image data. The extension alone does not determine the underlying file type.

### stat

`stat` provides detailed metadata about a file, including information such as size, timestamps, permissions, and inode information.

### du

`du` reports disk usage associated with files and directories.

    du -sh project

The `-s` option requests a summary, while `-h` commonly requests human-readable units.

### df

`df` reports available and used space on mounted file systems.

    df -h

The distinction between `df` and `du` is important. `df` describes file-system capacity, while `du` examines disk usage attributed to particular files and directories.

## Copying files

`cp` copies files.

A simple file copy is:

    cp source.txt destination.txt

Copying a file into a directory can be written as:

    cp source.txt destination/

Directories normally require recursive copying:

    cp -r source_directory destination_directory

The `-r` option means recursive.

Interactive and non-overwriting options can be useful when protecting existing data. For example, `cp -i` commonly asks before overwriting, while `cp -n` commonly prevents overwriting.

Exact option availability and behavior can vary between implementations, so local command documentation should be consulted when portability matters.

The Python equivalent demonstrated by the script is `shutil.copy2()`. It can copy file contents while preserving important metadata such as modification time.

## Moving and renaming

`mv` performs both moving and renaming.

Renaming a file:

    mv old_name.txt new_name.txt

Moving a file:

    mv report.txt documents/

The command changes the directory entry and path. The file's content is not inherently changed by a normal move.

The distinction between moving within the same file system and moving between file systems matters for performance. An operation within the same file system can often be implemented by changing directory entries, while a cross-file-system move may require copying the data and removing the original.

The `-i` option can provide interactive protection before overwriting a destination.

## Deleting files

`rm` removes file-system entries.

A file can be removed with:

    rm file.txt

A directory tree can be removed recursively with:

    rm -r directory/

The combination:

    rm -rf directory/

is especially powerful. `-r` enables recursive removal and `-f` commonly forces deletion without interactive confirmation.

This command should be treated as destructive and irreversible from the command's perspective.

A safer operational pattern is:

1. Identify the exact current directory with `pwd`.
2. Inspect the target with `ls` or `find`.
3. Verify the path and spelling.
4. Use interactive options when appropriate.
5. Avoid unnecessary root privileges.
6. Delete only the intended target.

The script intentionally performs deletion only inside its temporary practice workspace.

## Searching for files with find

`find` searches directory trees.

A basic search is:

    find . -type f

This finds regular files below the current directory.

File-name matching can be performed with:

    find . -name '*.txt'

The quotation marks are important. They prevent the shell from expanding `*.txt` before `find` receives it.

Useful tests include:

- `-type f` for regular files
- `-type d` for directories
- `-name` for file-name patterns
- `-size` for size-based searches
- `-mtime` for modification-time searches
- `-perm` for permission-related searches
- `-user` for ownership-related searches

Examples include:

    find . -type f -name '*.log'
    find . -type f -size +10M
    find . -type f -mtime -7

The exact meaning of time expressions should be checked against the local `find` implementation because time-based tests have specific unit and rounding semantics.

## Searching file contents with grep

`grep` searches text for patterns.

For example:

    grep 'ERROR' application.log

The two commands solve different problems:

- `find` answers where files matching conditions are located.
- `grep` answers which file contents contain a particular pattern.

Useful `grep` options include:

- `-n` displays line numbers.
- `-i` ignores case.
- `-r` searches directories recursively.
- `-v` selects lines that do not match.
- `-E` enables extended regular expressions.

Examples:

    grep -n 'ERROR' application.log
    grep -i 'error' application.log
    grep -r 'database' logs/

`grep` is particularly useful for logs, configuration files, source code, reports, and other text-oriented data.

## Wildcards

The shell supports pathname expansion through patterns commonly called globs.

Important patterns include:

- `*` matches zero or more characters.
- `?` matches one character.
- `[abc]` matches one character from the specified set.
- `[0-9]` matches one character from a specified range.

Examples:

    ls *.txt
    ls report?.csv
    ls image[0-9].png

Shell globs should not be confused with regular expressions. A pattern such as `*.txt` is a shell glob, while a regular expression uses a different syntax and matching model.

Quoting affects shell expansion. For example, a quoted pattern passed to `find` remains a pattern for `find` itself rather than being expanded by the shell.

## Redirection

Linux programs conventionally use three standard streams:

- `stdin` is standard input.
- `stdout` is standard output.
- `stderr` is standard error.

Redirection controls where these streams go.

Common forms include:

    command > output.txt
    command >> output.txt
    command 2> error.txt
    command 2>> error.txt
    command < input.txt

`>` replaces the destination contents.

`>>` appends.

`2>` redirects standard error.

`2>>` appends standard error.

`<` supplies a file as standard input.

Separating standard output from standard error is useful in automation because successful results and diagnostic messages often need different handling.

## Pipes

A pipe connects the standard output of one command to the standard input of another.

Example:

    grep 'ERROR' application.log | wc -l

Here, `grep` produces matching lines and `wc -l` counts them.

Pipelines encourage a Unix design principle in which each program performs a focused operation and the output of one program becomes input to another.

The pipe is different from redirection. Redirection sends a stream to or from a file. A pipe sends a stream between processes.

A pipeline can often replace a larger custom program for simple administrative tasks.

## Command substitution

Command substitution places the output of one command into another command.

A common shell form is:

    current_dir=$(pwd)

The result of `pwd` becomes part of the surrounding command.

Command substitution differs from a pipe. A pipe connects processes directly through streams, while command substitution captures command output as data for another shell expression.

## Text processing

Linux provides several utilities for processing text.

### sort

`sort` orders lines.

    sort names.txt

### uniq

`uniq` removes adjacent duplicate lines.

    sort names.txt | uniq

The sorting step is important when the goal is to eliminate all duplicate values, because `uniq` only recognizes duplicates that are next to one another.

### cut

`cut` extracts fields or character ranges.

For simple delimiter-separated data:

    cut -d',' -f1 data.csv

Basic `cut` usage is not a complete CSV parser. CSV permits quoted fields and embedded delimiters, so robust CSV processing may require a dedicated parser.

### tr

`tr` translates or deletes characters.

For example, translating lowercase ASCII letters to uppercase:

    tr 'a-z' 'A-Z'

### sed

`sed` performs stream-oriented transformations.

A common replacement form is:

    sed 's/old/new/g' file.txt

The command can perform powerful transformations, but complex text parsing can become difficult to maintain when a more structured processing method would be clearer.

### awk

`awk` processes records and fields.

A simple expression such as:

    awk '{print $1}' file.txt

prints the first whitespace-separated field.

Conditions can be applied:

    awk '$2 >= 29 {print $1, $2}' people.txt

`awk` is particularly useful for structured text where records and fields have a predictable format.

## Permissions

Linux permissions control who can read, modify, or execute a file.

Traditional permission classes are:

- user, meaning the file owner
- group, meaning members of the file's group
- others, meaning other users

Each class can have:

- `r` for read
- `w` for write
- `x` for execute

A permission string such as `rwxr-xr--` represents:

- owner: `rwx`
- group: `r-x`
- others: `r--`

Numeric permissions use octal values:

- read = 4
- write = 2
- execute = 1

Therefore:

- `7` means read, write, and execute.
- `5` means read and execute.
- `4` means read only.
- `0` means no permissions.

For example, `754` represents:

- owner: `rwx`
- group: `r-x`
- others: `r--`

`chmod` changes permissions.

Examples:

    chmod 640 file.txt
    chmod 755 script.sh
    chmod u+x script.sh

`chown` changes ownership, while `chgrp` changes group ownership.

Ownership changes frequently require elevated privileges, but `sudo` should not be used automatically whenever a command fails. The actual cause should first be identified.

## Executable files and shebangs

A shell script commonly begins with a shebang such as:

    #!/bin/sh

The shebang identifies the interpreter that should execute the script when the file is executed directly.

An executable script can be enabled with:

    chmod +x hello.sh

It can then be run with:

    ./hello.sh

The `./` explicitly identifies the file in the current directory.

The current directory is commonly not included in `PATH`. This is intentional because automatically executing a program from the current directory could create security risks.

## Hard links and symbolic links

Linux supports multiple ways to reference file data.

A hard link can be created with:

    ln original.txt hard_link.txt

A hard link is another directory entry referring to the same inode and underlying file data.

A symbolic link can be created with:

    ln -s original.txt symbolic_link.txt

A symbolic link is a separate object that stores a path to another object.

The principal distinction is:

- A hard link references the same inode.
- A symbolic link references a path.

Hard links normally cannot cross file-system boundaries and are generally not used to link directories for ordinary users.

Symbolic links can cross file-system boundaries and can reference directories. They can also become dangling when their targets are removed or moved.

The script uses `ls -li` to make inode relationships visible.

## Archives and compression

`tar` creates and extracts archives.

Common operations include:

    tar -cf archive.tar directory/
    tar -tf archive.tar
    tar -xf archive.tar

The important operation letters are:

- `c` for create
- `t` for list
- `x` for extract
- `f` for archive file

Compression can be combined with archiving.

For gzip-compressed tar archives:

    tar -czf archive.tar.gz directory/
    tar -xzf archive.tar.gz

The conceptual distinction is important: tar packages multiple files into an archive, while gzip compresses data.

Archives from untrusted sources should be inspected before extraction. Path traversal and unexpected absolute paths can create security problems if archive extraction is not controlled.

## Disk usage

`du` and `df` provide different views of storage.

`du` examines disk usage associated with files and directories:

    du -sh project

`df` reports free and used capacity of mounted file systems:

    df -h

Inode availability is another resource:

    df -i

A system can have free disk bytes but still fail to create new files when the available inodes have been exhausted.

This distinction becomes important on systems containing very large numbers of small files.

Sparse files also demonstrate why logical file size and physical disk usage are not always identical.

## Environment variables and PATH

The shell maintains environment variables used by programs.

Important variables commonly include:

- `HOME` for the user's home directory
- `PATH` for executable search locations
- `PWD` for the current directory in many shells
- `USER` for the current user in many environments

When a command such as `python` is entered, the shell searches directories listed in `PATH` to locate an executable.

Useful commands include:

    printenv PATH
    printenv HOME
    command -v python
    which python

`command -v` is especially useful in shell scripts because it checks how a command name resolves through the shell's command lookup rules.

PATH ordering matters. If two executable files have the same command name, the earlier matching directory can determine which one is executed.

Untrusted directories should not be added to PATH.

## Exit statuses

Programs normally return an exit status to the operating system.

The conventional interpretation is:

- `0` means successful completion.
- A nonzero value indicates failure or another non-success condition.

Shell scripts can use this status to make decisions.

Common shell operators include:

    command1 && command2
    command1 || command2
    command1 ; command2

`&&` normally runs the second command only if the first succeeds.

`||` normally runs the second command when the first fails.

`;` separates commands without requiring the first command to succeed.

The Python script demonstrates the same underlying process concept through `subprocess.run()` and its `returncode` attribute.

Checking exit statuses is essential for reliable automation. A command can produce output and still return a failure status.

## Quoting and special file names

Shell parsing happens before a command receives its arguments.

A path containing spaces must be quoted or escaped.

For example:

    cat 'quarterly report.txt'

Without quoting, the shell may interpret the two words as separate arguments.

Single quotes generally preserve their contents literally. Double quotes allow some shell expansion, such as variable expansion.

A robust shell scripting habit is to quote variables unless intentional word splitting or pathname expansion is required.

File names beginning with `-` require another precaution because many commands interpret such names as options.

The conventional option terminator is `--`:

    rm -- -strange-name.txt

This tells the command that subsequent arguments should be interpreted as operands rather than options.

## Advanced find operations

`find` can combine multiple tests and actions.

Examples include:

    find . -type f -name '*.log'
    find . -type f -size +10M
    find . -type f -mtime +30
    find . -type f -perm 600

The `-exec` action allows a command to operate on matched files:

    find . -type f -name '*.txt' -exec wc -l {} +

Here `{}` represents matched paths.

The `+` form allows multiple paths to be passed to each invocation, which can reduce process creation overhead compared with executing the command once for every file.

The choice between `-exec`, `xargs`, and pipelines depends on the task. When file names may contain spaces, tabs, or newlines, null-delimited techniques such as `-print0` with `xargs -0` provide safer handling than naïve newline-based processing.

## Command composition

The strength of the Linux command line often comes from combining focused utilities.

A typical workflow can include:

    mkdir -p project/logs
    touch project/logs/application.log
    grep -n 'ERROR' project/logs/application.log
    find project -type f
    du -sh project

A more advanced workflow can use `find` and `grep` together:

    find project -type f -name '*.log' -exec grep -n 'ERROR' {} +

The individual commands have distinct responsibilities:

- `find` discovers files.
- `grep` searches their content.
- `wc` counts results.
- `du` measures disk usage.
- `tar` packages the resulting directory.

This compositional model is a central characteristic of Unix-style command-line tools.

## Linux commands versus Python file APIs

Linux commands are highly effective for interactive work and concise system administration.

Python's standard library is often preferable when file operations are part of a larger application, require complex validation, need structured exception handling, or must be expressed in portable application logic.

The script demonstrates several conceptual equivalents:

| Linux command | Python concept |
|---|---|
| `pwd` | `Path.cwd()` |
| `ls` | `Path.iterdir()` |
| `mkdir` | `Path.mkdir()` |
| `touch` | `Path.touch()` |
| `cp` | `shutil.copy2()` |
| `mv` | `shutil.move()` |
| `rm` | `Path.unlink()` |
| `rm -r` | `shutil.rmtree()` |
| `find` | `Path.rglob()` |
| `cat` | `Path.read_text()` |
| `stat` | `Path.stat()` |

The choice should be based on clarity, safety, portability, maintainability, and the surrounding application architecture.

## Automation and subprocess safety

A major security issue occurs when untrusted data is inserted directly into a shell command.

Conceptually unsafe command construction looks like:

    "rm " + user_input

If a shell interprets the resulting string, special characters can change the meaning of the command.

Python's `subprocess.run()` can instead receive an argument list:

    subprocess.run(["rm", "--", filename], check=True)

When an argument list is supplied and shell execution is not requested, the filename is treated as an argument rather than being interpreted as shell syntax.

When shell syntax such as pipes or redirection is genuinely required, the shell must be involved deliberately and input must be handled carefully.

This distinction is important for scripts, web applications, automation systems, data-processing jobs, and deployment tooling.

## Security considerations

File-system commands can have significant security consequences.

### Least privilege

Commands should run with the minimum privileges required. Root access should not be treated as a general solution for command failures.

### Path traversal

Applications that accept paths from users must prevent paths such as `../../sensitive-file` from escaping an intended directory.

### Shell injection

Untrusted strings should not be concatenated into shell commands.

### Symbolic links

A path that appears to point to a safe file can instead resolve through a symbolic link to another location. Sensitive applications need deliberate symlink handling.

### Race conditions

A security-sensitive application should not assume that a file remains unchanged between checking it and using it. Appropriate atomic operations and operating-system APIs may be necessary.

### Destructive operations

Commands such as `rm -rf` should be treated as high-risk operations. Important data should have independent backups.

### Permissions

Files should not receive broader permissions than required. World-writable resources can create significant security problems.

### PATH manipulation

Untrusted directories should not be inserted into PATH because command resolution depends on PATH ordering.

## Atomic file updates

Applications that update important configuration or state files should avoid leaving partially written files visible to readers.

A common design is:

1. Write complete content to a temporary file.
2. Flush and synchronize where appropriate.
3. Atomically replace the target file.

The exact implementation depends on durability requirements and the underlying file system.

This principle is more reliable than assuming that a long sequence of shell commands is automatically atomic.

## Troubleshooting

When a command fails, the error should be diagnosed before privileges or force flags are added.

A useful sequence is:

1. Check the current directory with `pwd`.
2. Inspect the path with `ls -la`.
3. Determine the file type with `file`.
4. Inspect metadata with `stat`.
5. Inspect permissions and ownership.
6. Verify that the command exists with `command -v`.
7. Check the command's exit status.
8. Only then consider environmental or privilege-related causes.

Common failures include:

- `command not found`
- `No such file or directory`
- `Permission denied`
- `Is a directory`
- `Not a directory`
- `File exists`

`sudo` does not fix incorrect paths, missing programs, bad syntax, or most logical errors.

## Common mistakes

### Confusing relative and absolute paths

A relative path depends on the current directory. Use `pwd` whenever the current location is uncertain.

### Forgetting case sensitivity

Linux treats different capitalization as different names.

### Overwriting with redirection

`>` replaces existing contents. Use `>>` when appending is intended.

### Forgetting recursive operations

Directories require recursive options for many `cp` and `rm` operations.

### Using `rm -rf` casually

Recursive forced deletion removes safety mechanisms and can cause substantial data loss.

### Assuming `uniq` finds all duplicates

`uniq` removes adjacent duplicates. Sorting is commonly required first.

### Confusing shell globs and regular expressions

`*.txt` is a shell-style pattern. It is not a regular expression.

### Parsing `ls` output

File names can contain unusual characters. Structured tools and direct APIs are safer for automation.

### Ignoring exit statuses

A command's output does not necessarily mean that it succeeded.

### Using excessive privileges

Running commands as root increases the consequences of mistakes.

### Assuming all Linux commands behave identically

GNU/Linux, BSD, BusyBox, and other Unix-like environments can provide different command implementations and options.

## Performance considerations

Command-line performance depends on data volume, process creation, file-system characteristics, storage hardware, and the design of the workflow.

Important considerations include:

- Prefer grouped `find -exec ... {} +` over starting a new process for every file when appropriate.
- Avoid repeatedly scanning very large directory trees unnecessarily.
- Use `head` or `tail` instead of reading entire large files when only a portion is needed.
- Pipelines can process streams without requiring every intermediate result to be stored on disk.
- `du` over a very large tree can be expensive because many directory entries must be inspected.
- Cross-file-system moves can require copying file contents and therefore can be much slower than same-file-system renames.
- Compression consumes CPU time in exchange for reduced storage or transfer size.
- Searching with appropriate file-name and directory constraints can significantly reduce unnecessary work.

For large-scale application logic, a direct programming API may be more efficient and easier to control than repeatedly launching external commands.

## Production considerations

Interactive commands and production automation have different requirements.

Production file operations should generally include:

- explicit path handling
- input validation
- least-privilege execution
- exit-status checking
- predictable logging
- controlled permissions
- careful treatment of symbolic links
- appropriate backup and recovery mechanisms
- atomic update strategies where required
- portability testing when multiple operating systems or distributions are supported

Commands should be tested in a controlled environment before being applied to production data.

## Integrated practice workflow

The script includes an integrated example that creates a small project structure, places log files and documentation into it, searches for log files, finds `ERROR` records, counts matching lines, and measures directory usage.

The conceptual workflow is:

    find project -type f -print

followed by targeted content inspection:

    find project -type f -name '*.log' -exec grep -n 'ERROR' {} +

and disk inspection:

    du -sh project

This illustrates how Linux commands can be combined according to their individual responsibilities instead of relying on one large command.

## Practice exercises

The script includes practical exercises covering:

- navigation
- nested directory creation
- text file creation
- copying
- moving and renaming
- searching with `find`
- content searching with `grep`
- pipelines with `wc`
- permission inspection and modification
- symbolic links
- archive creation and extraction
- safe recursive deletion
- integrated project and log processing

The exercises are designed to be performed inside a disposable practice directory so that destructive commands can be studied without intentionally targeting personal or production data.

## Command reference

| Command | Primary purpose | Example |
|---|---|---|
| `pwd` | Print working directory | `pwd` |
| `ls` | List directory contents | `ls -la` |
| `cd` | Change directory | `cd /tmp` |
| `mkdir` | Create directories | `mkdir -p project/data` |
| `touch` | Create files or update timestamps | `touch notes.txt` |
| `cp` | Copy files and directories | `cp -r src backup` |
| `mv` | Move or rename files | `mv old.txt new.txt` |
| `rm` | Remove files and directories | `rm -r old_directory` |
| `cat` | Display file contents | `cat notes.txt` |
| `less` | Interactively inspect text | `less application.log` |
| `head` | Display the beginning of a file | `head -n 20 file.txt` |
| `tail` | Display the end of a file | `tail -n 20 file.txt` |
| `wc` | Count lines, words, and bytes | `wc -l file.txt` |
| `file` | Identify file type | `file image.png` |
| `stat` | Display detailed metadata | `stat file.txt` |
| `find` | Search directory trees | `find . -type f -name '*.txt'` |
| `grep` | Search text for patterns | `grep -n 'ERROR' app.log` |
| `sort` | Sort lines | `sort names.txt` |
| `uniq` | Remove adjacent duplicate lines | `sort names.txt \| uniq` |
| `cut` | Extract fields or character ranges | `cut -d',' -f1 data.csv` |
| `tr` | Translate or delete characters | `tr 'a-z' 'A-Z'` |
| `sed` | Transform streams of text | `sed 's/old/new/g' file` |
| `awk` | Process records and fields | `awk '{print $1}' file` |
| `chmod` | Change permissions | `chmod 640 file.txt` |
| `chown` | Change ownership | `chown user file.txt` |
| `chgrp` | Change group ownership | `chgrp developers file.txt` |
| `ln` | Create links | `ln -s target link` |
| `tar` | Create and extract archives | `tar -czf backup.tar.gz project` |
| `gzip` | Compress data | `gzip file.txt` |
| `df` | Show file-system capacity | `df -h` |
| `du` | Show disk usage | `du -sh project` |
| `command -v` | Resolve a command | `command -v python` |
| `printenv` | Display environment variables | `printenv PATH` |

## Relationship between the commands

The commands covered in the script can be understood as groups of related responsibilities.

Navigation commands establish context:

`pwd`, `ls`, and `cd`

File-system mutation commands create or modify directory entries:

`mkdir`, `touch`, `cp`, `mv`, and `rm`

Inspection commands examine content or metadata:

`cat`, `less`, `head`, `tail`, `wc`, `file`, `stat`, `du`, and `df`

Search commands locate files or content:

`find` and `grep`

Text-processing commands transform or analyze streams:

`sort`, `uniq`, `cut`, `tr`, `sed`, and `awk`

Permission and identity commands control access:

`chmod`, `chown`, and `chgrp`

Link commands provide alternative references:

`ln`

Archive and compression commands package data:

`tar` and `gzip`

Shell mechanisms connect these tools:

pipes, redirection, quoting, command substitution, exit statuses, and environment variables.

This separation of responsibilities is what allows relatively small utilities to form sophisticated command-line workflows.
