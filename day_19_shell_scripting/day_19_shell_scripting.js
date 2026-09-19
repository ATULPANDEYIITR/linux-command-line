#!/usr/bin/env node
"use strict";

/*
 * Shell Scripting with Bash: JavaScript Companion
 *
 * This file uses JavaScript to demonstrate concepts that complement Bash:
 * process execution, argument vectors, environment inheritance, pipelines,
 * asynchronous orchestration, validation, filesystem automation, logging,
 * retries, concurrency limits, and deployment-style workflow design.
 *
 * Run with:
 *     node shell-scripting.js
 *
 * No external npm packages are required.
 */

const fs = require("fs");
const fsp = require("fs/promises");
const os = require("os");
const path = require("path");
const crypto = require("crypto");
const { spawn, execFile } = require("child_process");
const { promisify } = require("util");

const execFileAsync = promisify(execFile);

function section(title) {
    console.log("\n" + "=".repeat(78));
    console.log(title);
    console.log("=".repeat(78));
}

function subsection(title) {
    console.log("\n" + "-".repeat(78));
    console.log(title);
    console.log("-".repeat(78));
}

function show(label, value) {
    console.log(`${label}:`, value);
}


// ---------------------------------------------------------------------------
// 1. Shell and process fundamentals
// ---------------------------------------------------------------------------

function demonstrateShellFundamentals() {
    section("1. Shell and process fundamentals");

    console.log(`
Bash is a command interpreter. JavaScript normally does not replace Bash;
instead, Node.js can orchestrate operating-system processes.

A Bash command such as:

    printf '%s\\n' "hello"

can be launched by a Node.js program using child_process.

A critical distinction is that spawn/execFile can execute a program without
asking a shell to interpret a constructed command string.
`);

    console.log("Node executable:", process.execPath);
    console.log("Platform:", process.platform);
    console.log("CPU architecture:", process.arch);
    console.log("Current directory:", process.cwd());
}


// ---------------------------------------------------------------------------
// 2. Variables and environment
// ---------------------------------------------------------------------------

function demonstrateVariablesAndEnvironment() {
    section("2. Variables and environment variables");

    const applicationName = "inventory-api";
    const deploymentVersion = "2026.09.19";

    console.log("Application:", applicationName);
    console.log("Version:", deploymentVersion);

    console.log("\nImportant environment variables:");
    for (const name of ["HOME", "PATH", "SHELL", "USER", "PWD"]) {
        console.log(`${name}: ${process.env[name] ?? "<not set>"}`);
    }

    console.log(`
In Bash:

    APP_ENV="production"
    export APP_ENV

The exported variable becomes part of the environment inherited by child
processes. Node.js exposes the current process environment through
process.env.
`);
}


// ---------------------------------------------------------------------------
// 3. Safe process execution
// ---------------------------------------------------------------------------

async function demonstrateSafeProcessExecution() {
    section("3. Safe process execution");

    console.log(`
Prefer argument vectors when executing commands from application code.

Conceptually safer:

    execFile("printf", ["%s\\\\n", userValue])

than constructing:

    exec("printf '%s' " + userValue)

The second approach may involve shell parsing and can become dangerous when
user-controlled data is incorporated into a command.
`);

    const result = await execFileAsync(
        process.platform === "win32" ? "node" : "printf",
        process.platform === "win32"
            ? ["-e", "console.log('child process output')"]
            : ["%s\n", "child process output"]
    );

    console.log("Captured stdout:", result.stdout.trim());
}


// ---------------------------------------------------------------------------
// 4. Command arguments
// ---------------------------------------------------------------------------

function demonstrateArguments() {
    section("4. Command-line arguments");

    console.log(`
A Bash script receives:

    $0   script name
    $1   first argument
    $2   second argument
    $#   argument count
    "$@" all arguments individually

Node.js provides a similar concept through process.argv.
`);

    console.log("process.argv:", process.argv);
    console.log("User argument count:", Math.max(0, process.argv.length - 2));
}


// ---------------------------------------------------------------------------
// 5. Validation
// ---------------------------------------------------------------------------

function validateEnvironment(environment) {
    const allowed = new Set([
        "development",
        "testing",
        "production",
    ]);

    if (!allowed.has(environment)) {
        throw new Error(
            `Invalid environment "${environment}". ` +
            `Allowed values: ${[...allowed].join(", ")}`
        );
    }

    return true;
}

function demonstrateValidation() {
    section("5. Input validation");

    const candidates = [
        "development",
        "production",
        "unknown",
        "testing",
    ];

    for (const candidate of candidates) {
        try {
            validateEnvironment(candidate);
            console.log(`${candidate}: valid`);
        } catch (error) {
            console.log(`${candidate}: invalid -> ${error.message}`);
        }
    }

    console.log(`
Bash validation should happen before external input is used in commands.

Do not use eval on untrusted text. In Node.js, the same principle applies to
child-process execution: avoid shell interpretation when direct execution
with explicit arguments is sufficient.
`);
}


// ---------------------------------------------------------------------------
// 6. Filesystem automation
// ---------------------------------------------------------------------------

async function demonstrateFilesystemAutomation() {
    section("6. Filesystem automation");

    const temporaryDirectory = await fsp.mkdtemp(
        path.join(os.tmpdir(), "shell-study-")
    );

    try {
        const source = path.join(temporaryDirectory, "source.txt");
        const archiveDirectory = path.join(
            temporaryDirectory,
            "archive"
        );
        const destination = path.join(
            archiveDirectory,
            "source.txt"
        );

        await fsp.mkdir(archiveDirectory, { recursive: true });
        await fsp.writeFile(source, "important data\n", "utf8");
        await fsp.copyFile(source, destination);

        console.log("Temporary workspace:", temporaryDirectory);
        console.log(
            "Destination exists:",
            fs.existsSync(destination)
        );
        console.log(
            "Destination content:",
            (await fsp.readFile(destination, "utf8")).trim()
        );
    } finally {
        await fsp.rm(temporaryDirectory, {
            recursive: true,
            force: true,
        });
    }
}


// ---------------------------------------------------------------------------
// 7. Exit statuses
// ---------------------------------------------------------------------------

async function demonstrateExitStatus() {
    section("7. Exit status and error handling");

    console.log(`
Unix programs normally communicate success or failure through an integer
exit status. Zero conventionally means success; nonzero means failure.

Node.js receives process failures as rejected promises or error events when
using its process APIs.
`);

    try {
        await execFileAsync(
            process.platform === "win32" ? "node" : "sh",
            process.platform === "win32"
                ? ["-e", "process.exit(0)"]
                : ["-c", "exit 0"]
        );

        console.log("Command exit status: 0");
    } catch (error) {
        console.log("Command failed:", error.message);
    }

    try {
        await execFileAsync(
            process.platform === "win32" ? "node" : "sh",
            process.platform === "win32"
                ? ["-e", "process.exit(7)"]
                : ["-c", "exit 7"]
        );
    } catch (error) {
        console.log("Expected nonzero command status:", error.code);
    }
}


// ---------------------------------------------------------------------------
// 8. Pipelines
// ---------------------------------------------------------------------------

function demonstratePipelineConcept() {
    section("8. Pipelines and data flow");

    console.log(`
A Bash pipeline:

    command1 | command2 | command3

connects stdout of one process to stdin of the next.

Node.js can construct the same topology with child_process.spawn and stream
pipes. The example below demonstrates the data-processing idea entirely
in memory.
`);

    const lines = [
        "INFO application started",
        "ERROR database unavailable",
        "INFO retrying",
        "ERROR timeout",
        "INFO recovered",
    ];

    const filtered = lines
        .filter(line => line.includes("ERROR"))
        .map(line => line.toUpperCase());

    console.log("Pipeline input:");
    console.log(lines);
    console.log("Pipeline output:");
    console.log(filtered);
}


// ---------------------------------------------------------------------------
// 9. Functions
// ---------------------------------------------------------------------------

function greet(name) {
    return `Hello, ${name}`;
}

function addNumbers(first, second) {
    return first + second;
}

function demonstrateFunctions() {
    section("9. Functions");

    console.log("Greeting:", greet("Atul"));
    console.log("Addition:", addNumbers(20, 22));

    console.log(`
Bash functions group reusable shell operations:

    deploy() {
        local environment="$1"
        ...
    }

A function's return value in Bash is normally an exit status. Text output
can be captured with command substitution:

    result="$(function_name)"
`);
}


// ---------------------------------------------------------------------------
// 10. Arrays and structured data
// ---------------------------------------------------------------------------

function demonstrateArraysAndObjects() {
    section("10. Arrays and associative data");

    const servers = ["web01", "web02", "web03"];

    // JavaScript objects provide a natural comparison to Bash associative
    // arrays declared with: declare -A ports
    const ports = {
        http: 80,
        https: 443,
        ssh: 22,
    };

    console.log("Indexed array:", servers);
    console.log("First server:", servers[0]);
    console.log("Array length:", servers.length);
    console.log("Associative data:", ports);
}


// ---------------------------------------------------------------------------
// 11. Pattern matching
// ---------------------------------------------------------------------------

function demonstratePatternMatching() {
    section("11. Globs and regular expressions");

    console.log(`
Shell globbing and regular expressions are different pattern systems.

A Bash glob:
    *.log

A Bash regular expression:
    [[ "$name" =~ ^.*\\.log$ ]]

JavaScript's regular expression engine can demonstrate the second concept.
`);

    const filenames = [
        "app.log",
        "database.txt",
        "worker.log",
        "README.md",
    ];

    const logPattern = /^.*\.log$/;

    console.log(
        "Regex matches:",
        filenames.filter(name => logPattern.test(name))
    );
}


// ---------------------------------------------------------------------------
// 12. Async execution
// ---------------------------------------------------------------------------

function runCommand(command, args = []) {
    return new Promise((resolve, reject) => {
        const child = spawn(command, args, {
            stdio: ["ignore", "pipe", "pipe"],
        });

        let stdout = "";
        let stderr = "";

        child.stdout.on("data", chunk => {
            stdout += chunk;
        });

        child.stderr.on("data", chunk => {
            stderr += chunk;
        });

        child.on("error", reject);

        child.on("close", code => {
            if (code === 0) {
                resolve({ code, stdout, stderr });
            } else {
                const error = new Error(
                    `Command exited with status ${code}`
                );
                error.code = code;
                error.stdout = stdout;
                error.stderr = stderr;
                reject(error);
            }
        });
    });
}

async function demonstrateAsyncExecution() {
    section("12. Asynchronous process execution");

    console.log(`
Bash background execution can look like:

    task_a &
    task_b &
    wait

Node.js uses asynchronous APIs naturally. Promises allow several independent
operations to be coordinated without blocking the JavaScript event loop.
`);

    const command = process.platform === "win32"
        ? process.execPath
        : "printf";

    const args = process.platform === "win32"
        ? ["-e", "console.log('async child')"]
        : ["%s\n", "async child"];

    const result = await runCommand(command, args);

    console.log("Exit code:", result.code);
    console.log("Output:", result.stdout.trim());
}


// ---------------------------------------------------------------------------
// 13. Retry and exponential backoff
// ---------------------------------------------------------------------------

function sleep(milliseconds) {
    return new Promise(resolve => setTimeout(resolve, milliseconds));
}

async function retry(operation, options = {}) {
    const {
        attempts = 4,
        initialDelay = 50,
        multiplier = 2,
    } = options;

    let delay = initialDelay;

    for (let attempt = 1; attempt <= attempts; attempt += 1) {
        try {
            return await operation(attempt);
        } catch (error) {
            if (attempt === attempts) {
                throw error;
            }

            console.log(
                `Attempt ${attempt} failed; retrying in ${delay}ms`
            );

            await sleep(delay);
            delay *= multiplier;
        }
    }

    throw new Error("Unreachable retry state");
}

async function demonstrateRetries() {
    section("13. Retry strategy");

    let attemptCounter = 0;

    const result = await retry(
        async attempt => {
            attemptCounter += 1;

            if (attempt < 3) {
                throw new Error("simulated transient failure");
            }

            return "operation succeeded";
        },
        {
            attempts: 4,
            initialDelay: 20,
            multiplier: 2,
        }
    );

    console.log("Result:", result);
    console.log("Attempts:", attemptCounter);
}


// ---------------------------------------------------------------------------
// 14. Concurrency limits
// ---------------------------------------------------------------------------

async function mapWithConcurrency(items, limit, worker) {
    if (!Number.isInteger(limit) || limit < 1) {
        throw new RangeError("Concurrency limit must be at least 1");
    }

    const results = new Array(items.length);
    let nextIndex = 0;

    async function workerLoop() {
        while (true) {
            const index = nextIndex++;

            if (index >= items.length) {
                return;
            }

            results[index] = await worker(items[index], index);
        }
    }

    const workerCount = Math.min(limit, items.length);

    await Promise.all(
        Array.from(
            { length: workerCount },
            () => workerLoop()
        )
    );

    return results;
}

async function demonstrateConcurrencyLimits() {
    section("14. Bounded concurrency");

    console.log(`
Starting unlimited background jobs can exhaust CPU, memory, file
descriptors, network connections, or service capacity.

The same design concern exists with Bash background jobs. A production
script should bound concurrent work rather than creating thousands of
uncontrolled processes.
`);

    const tasks = [
        "database-check",
        "cache-check",
        "filesystem-check",
        "api-check",
        "queue-check",
    ];

    const results = await mapWithConcurrency(
        tasks,
        2,
        async task => {
            await sleep(15);
            return `${task}: completed`;
        }
    );

    console.log(results);
}


// ---------------------------------------------------------------------------
// 15. Hashes and integrity
// ---------------------------------------------------------------------------

function demonstrateIntegrity() {
    section("15. Cryptographic checksums");

    const artifact = Buffer.from("release artifact\n", "utf8");

    const digest = crypto
        .createHash("sha256")
        .update(artifact)
        .digest("hex");

    console.log("SHA-256:", digest);
    console.log("Digest length:", digest.length);

    console.log(`
Bash commonly uses:

    sha256sum artifact.tar.gz

A cryptographic hash detects changes but does not independently establish
authenticity. Authenticity requires a trusted distribution mechanism,
signature, or comparable trust relationship.
`);
}


// ---------------------------------------------------------------------------
// 16. Temporary resources and cleanup
// ---------------------------------------------------------------------------

async function demonstrateCleanup() {
    section("16. Cleanup and temporary resources");

    const temporaryDirectory = await fsp.mkdtemp(
        path.join(os.tmpdir(), "cleanup-study-")
    );

    let cleanupCompleted = false;

    try {
        const temporaryFile = path.join(
            temporaryDirectory,
            "work.tmp"
        );

        await fsp.writeFile(temporaryFile, "temporary\n");
        console.log("Created:", temporaryFile);
    } finally {
        await fsp.rm(temporaryDirectory, {
            recursive: true,
            force: true,
        });

        cleanupCompleted = true;
    }

    console.log("Cleanup completed:", cleanupCompleted);

    console.log(`
Bash commonly implements cleanup with:

    cleanup() {
        rm -rf -- "$temporary_directory"
    }

    trap cleanup EXIT

The same principle applies to JavaScript: resource cleanup belongs in
finally blocks or equivalent lifecycle handlers.
`);
}


// ---------------------------------------------------------------------------
// 17. Idempotence
// ---------------------------------------------------------------------------

async function demonstrateIdempotence() {
    section("17. Idempotent automation");

    const temporaryDirectory = await fsp.mkdtemp(
        path.join(os.tmpdir(), "idempotence-study-")
    );

    try {
        const applicationDirectory = path.join(
            temporaryDirectory,
            "application"
        );

        // recursive:true makes repeated execution safe when the desired
        // directory already exists, similar to Bash's mkdir -p.
        await fsp.mkdir(applicationDirectory, { recursive: true });
        await fsp.mkdir(applicationDirectory, { recursive: true });
        await fsp.mkdir(applicationDirectory, { recursive: true });

        console.log(
            "Directory still exists after repeated operations:",
            fs.existsSync(applicationDirectory)
        );
    } finally {
        await fsp.rm(temporaryDirectory, {
            recursive: true,
            force: true,
        });
    }
}


// ---------------------------------------------------------------------------
// 18. Configuration object
// ---------------------------------------------------------------------------

class DeploymentConfig {
    constructor({
        application,
        version,
        environment,
        retentionDays = 7,
    }) {
        this.application = application;
        this.version = version;
        this.environment = environment;
        this.retentionDays = retentionDays;
    }

    validate() {
        validateEnvironment(this.environment);

        if (!/^[A-Za-z0-9._-]+$/.test(this.application)) {
            throw new Error("Invalid application name");
        }

        if (!/^[A-Za-z0-9._-]+$/.test(this.version)) {
            throw new Error("Invalid version");
        }

        if (!Number.isInteger(this.retentionDays) ||
            this.retentionDays < 1) {
            throw new Error("Retention must be a positive integer");
        }

        return true;
    }
}

function demonstrateConfiguration() {
    section("18. Configuration-driven design");

    const config = new DeploymentConfig({
        application: "inventory-api",
        version: "2026.09.19",
        environment: "production",
        retentionDays: 14,
    });

    config.validate();

    console.log("Validated configuration:", config);

    console.log(`
Configuration can come from:
- command-line arguments,
- environment variables,
- configuration files,
- service metadata.

Secrets should not be embedded in source code or printed into logs.
`);
}


// ---------------------------------------------------------------------------
// 19. Deployment case study
// ---------------------------------------------------------------------------

class DeploymentAutomation {
    constructor(config) {
        this.config = config;
        this.logs = [];
        this.healthChecks = [];
        this.deployedVersion = null;
    }

    log(level, message) {
        const timestamp = new Date().toISOString();
        const entry = `${timestamp} [${level}] ${message}`;

        this.logs.push(entry);
        console.log(entry);
    }

    validate() {
        this.config.validate();
        this.log("INFO", "configuration validated");
    }

    prepare() {
        this.log("INFO", "deployment workspace prepared");
    }

    verifyArtifact() {
        this.log("INFO", "artifact integrity verified");
    }

    deploy() {
        this.deployedVersion = this.config.version;

        this.log(
            "INFO",
            `${this.config.application} deployed at ` +
            `${this.config.version}`
        );
    }

    healthCheck() {
        const checks = [
            "process",
            "port",
            "application",
        ];

        for (const check of checks) {
            this.healthChecks.push(check);
            this.log(
                "INFO",
                `health check passed: ${check}`
            );
        }

        return true;
    }

    rollback(previousVersion) {
        this.deployedVersion = previousVersion;

        this.log(
            "WARNING",
            `rollback completed to ${previousVersion}`
        );
    }

    async run(previousVersion) {
        this.validate();
        this.prepare();
        this.verifyArtifact();
        this.deploy();

        const healthy = this.healthCheck();

        if (!healthy) {
            this.rollback(previousVersion);
            return false;
        }

        this.log("INFO", "deployment completed successfully");
        return true;
    }
}

async function demonstrateDeploymentCaseStudy() {
    section("19. Industry-style deployment automation");

    console.log(`
A deployment shell script often coordinates:
- argument parsing,
- configuration validation,
- artifact verification,
- filesystem operations,
- service commands,
- health checks,
- logging,
- cleanup,
- rollback.

JavaScript can demonstrate the same orchestration architecture while using
Node.js process and filesystem APIs.
`);

    const config = new DeploymentConfig({
        application: "inventory-api",
        version: "2026.09.19",
        environment: "production",
        retentionDays: 14,
    });

    const deployment = new DeploymentAutomation(config);

    const success = await deployment.run("2026.09.18");

    console.log("Deployment success:", success);
    console.log("Deployed version:", deployment.deployedVersion);
    console.log("Health checks:", deployment.healthChecks);
}


// ---------------------------------------------------------------------------
// 20. Security comparison
// ---------------------------------------------------------------------------

function demonstrateSecurityPractices() {
    section("20. Shell automation security");

    const unsafeConcept = `shell command containing untrusted input`;
    const safeConcept = [
        "program",
        "--option",
        "validated-user-value",
    ];

    console.log("Unsafe conceptual approach:", unsafeConcept);
    console.log("Safer argument-vector approach:", safeConcept);

    console.log(`
Important shell security practices:
- quote expansions,
- avoid eval,
- avoid unnecessary shell interpretation,
- use arrays for command arguments,
- validate allowed values,
- use -- before filenames where supported,
- protect secrets,
- use least-privilege permissions,
- avoid predictable temporary filenames,
- do not trust command output as authorization data.
`);
}


// ---------------------------------------------------------------------------
// 21. Performance comparison
// ---------------------------------------------------------------------------

function demonstratePerformance() {
    section("21. Performance considerations");

    const values = Array.from({ length: 100000 }, (_, index) => index);

    const start = process.hrtime.bigint();

    const result = values.reduce(
        (total, value) => total + value * value,
        0
    );

    const elapsedNanoseconds =
        process.hrtime.bigint() - start;

    console.log("Processed values:", values.length);
    console.log("Result:", result);
    console.log(
        "Elapsed time (ms):",
        Number(elapsedNanoseconds) / 1_000_000
    );

    console.log(`
Shell excels at orchestration and composition of existing Unix tools.

Repeatedly starting external processes inside a large data-processing loop
can be expensive. For complex algorithms, an in-process language may be
more appropriate.

A useful design boundary is:

    Shell -> orchestration
    Application language -> complex computation and state
`);
}


// ---------------------------------------------------------------------------
// 22. Common Bash mistakes
// ---------------------------------------------------------------------------

function demonstrateCommonMistakes() {
    section("22. Common Bash mistakes");

    const comparisons = [
        ["Unquoted variable", 'rm $file'],
        ["Quoted variable", 'rm -- "$file"'],
        ["Unsafe evaluation", 'eval "$input"'],
        ["Argument vector", '"${command[@]}"'],
        ["Fragile file loop", 'for file in $(ls)'],
        ["Safer file loop", 'for file in *; do ...; done'],
        ["Explicit test", 'if command; then ...; fi'],
        ["Pipeline reliability", 'set -o pipefail'],
    ];

    for (const [name, example] of comparisons) {
        console.log(`${name}: ${example}`);
    }
}


// ---------------------------------------------------------------------------
// 23. Main
// ---------------------------------------------------------------------------

async function main() {
    console.log(`
SHELL SCRIPTING WITH BASH
=========================

JavaScript companion demonstrating process orchestration, filesystem
automation, asynchronous execution, validation, security, and deployment
architecture.
`);

    demonstrateShellFundamentals();
    demonstrateVariablesAndEnvironment();
    await demonstrateSafeProcessExecution();
    demonstrateArguments();
    demonstrateValidation();
    await demonstrateFilesystemAutomation();
    await demonstrateExitStatus();
    demonstratePipelineConcept();
    demonstrateFunctions();
    demonstrateArraysAndObjects();
    demonstratePatternMatching();
    await demonstrateAsyncExecution();
    await demonstrateRetries();
    await demonstrateConcurrencyLimits();
    demonstrateIntegrity();
    await demonstrateCleanup();
    await demonstrateIdempotence();
    demonstrateConfiguration();
    await demonstrateDeploymentCaseStudy();
    demonstrateSecurityPractices();
    demonstratePerformance();
    demonstrateCommonMistakes();

    section("End of JavaScript companion");
    console.log("All demonstrations completed.");
}

main().catch(error => {
    console.error("Fatal error:", error.message);
    process.exitCode = 1;
});
