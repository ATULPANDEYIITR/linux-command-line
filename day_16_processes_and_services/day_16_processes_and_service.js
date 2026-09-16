"use strict";

/*
 * Processes and Services
 * ======================
 *
 * JavaScript perspective:
 * - Node.js processes
 * - child_process
 * - process identity and environment
 * - signals
 * - asynchronous process management
 * - worker threads
 * - process isolation
 * - IPC
 * - graceful shutdown
 * - timeouts
 * - monitoring
 * - service-style application design
 *
 * Run with:
 *     node processes-and-services.js
 *
 * The examples use only Node.js built-in modules.
 */

const os = require("os");
const fs = require("fs");
const path = require("path");
const {
    spawn,
    execFile,
    fork
} = require("child_process");
const {
    Worker,
    isMainThread,
    parentPort,
    workerData
} = require("worker_threads");


// ---------------------------------------------------------------------------
// Worker-thread section
// ---------------------------------------------------------------------------

if (!isMainThread) {
    // Worker threads share the process but have separate JavaScript execution
    // contexts. They are useful for CPU-intensive JavaScript work.
    if (workerData && workerData.type === "prime-count") {
        function isPrime(number) {
            if (number < 2) return false;
            if (number === 2) return true;
            if (number % 2 === 0) return false;

            for (let divisor = 3; divisor * divisor <= number; divisor += 2) {
                if (number % divisor === 0) return false;
            }

            return true;
        }

        let count = 0;

        for (let number = workerData.start; number < workerData.end; number++) {
            if (isPrime(number)) count++;
        }

        parentPort.postMessage({
            start: workerData.start,
            end: workerData.end,
            count
        });
    }

    return;
}


// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function heading(title) {
    console.log("\n" + "=".repeat(78));
    console.log(title);
    console.log("=".repeat(78));
}

function sleep(milliseconds) {
    return new Promise(resolve => setTimeout(resolve, milliseconds));
}


// ---------------------------------------------------------------------------
// Process identity
// ---------------------------------------------------------------------------

function demonstrateProcessIdentity() {
    heading("1. Node.js process identity");

    console.log("PID:", process.pid);
    console.log("Parent PID:", process.ppid);
    console.log("Executable:", process.execPath);
    console.log("Node version:", process.version);
    console.log("Platform:", process.platform);
    console.log("Architecture:", process.arch);
    console.log("Working directory:", process.cwd());
    console.log("Arguments:", process.argv);
    console.log("CPU count:", os.cpus().length);

    // Environment variables are inherited by default from the parent process.
    console.log("PATH exists:", Boolean(process.env.PATH));
}


// ---------------------------------------------------------------------------
// Memory and resource inspection
// ---------------------------------------------------------------------------

function demonstrateMemoryMetrics() {
    heading("2. Process memory metrics");

    const memory = process.memoryUsage();

    console.log("RSS:", memory.rss);
    console.log("Heap total:", memory.heapTotal);
    console.log("Heap used:", memory.heapUsed);
    console.log("External:", memory.external);
    console.log("Array buffers:", memory.arrayBuffers);

    // os.freemem() describes system memory, not only this process.
    console.log("System free memory:", os.freemem());
    console.log("System total memory:", os.totalmem());
}


// ---------------------------------------------------------------------------
// Child process creation
// ---------------------------------------------------------------------------

function runExecFile(command, argumentsList, timeout = 3000) {
    return new Promise((resolve, reject) => {
        // execFile avoids invoking a shell by default. This is safer than
        // interpolating untrusted values into a shell command.
        execFile(
            command,
            argumentsList,
            {
                encoding: "utf8",
                timeout
            },
            (error, stdout, stderr) => {
                if (error) {
                    reject({
                        error,
                        stdout,
                        stderr
                    });
                    return;
                }

                resolve({
                    stdout,
                    stderr
                });
            }
        );
    });
}

async function demonstrateChildProcess() {
    heading("3. Creating a child process");

    const nodeExecutable = process.execPath;

    try {
        const result = await runExecFile(
            nodeExecutable,
            [
                "-e",
                "console.log('child process:', process.pid)"
            ]
        );

        console.log("Child stdout:", result.stdout.trim());
        console.log("Child stderr:", result.stderr.trim() || "<empty>");
    } catch (result) {
        console.error("Child process failed:", result.error.message);
    }
}


// ---------------------------------------------------------------------------
// Streaming process output
// ---------------------------------------------------------------------------

function demonstrateSpawn() {
    heading("4. Streaming child-process output");

    return new Promise((resolve, reject) => {
        const child = spawn(
            process.execPath,
            [
                "-e",
                `
                let count = 0;
                const timer = setInterval(() => {
                    console.log("child tick", ++count);
                    if (count === 3) {
                        clearInterval(timer);
                    }
                }, 50);
                `
            ],
            {
                stdio: ["ignore", "pipe", "pipe"]
            }
        );

        child.stdout.on("data", data => {
            process.stdout.write("STDOUT > " + data);
        });

        child.stderr.on("data", data => {
            process.stderr.write("STDERR > " + data);
        });

        child.on("error", error => {
            reject(error);
        });

        child.on("close", (code, signal) => {
            console.log("Child closed:", { code, signal });
            resolve();
        });
    });
}


// ---------------------------------------------------------------------------
// Timeouts and termination
// ---------------------------------------------------------------------------

function demonstrateTimeout() {
    heading("5. Child-process timeout");

    return new Promise(resolve => {
        const child = spawn(
            process.execPath,
            [
                "-e",
                "setTimeout(() => console.log('finished'), 10000)"
            ],
            {
                stdio: ["ignore", "pipe", "pipe"]
            }
        );

        const timeout = setTimeout(() => {
            console.log("Timeout reached; sending termination signal.");
            child.kill("SIGTERM");
        }, 200);

        child.stdout.on("data", data => {
            process.stdout.write(data);
        });

        child.on("close", (code, signal) => {
            clearTimeout(timeout);
            console.log("Final status:", { code, signal });
            resolve();
        });
    });
}


// ---------------------------------------------------------------------------
// Signals
// ---------------------------------------------------------------------------

function demonstrateSignals() {
    heading("6. Signals");

    return new Promise(resolve => {
        const handler = () => {
            console.log("Parent received SIGUSR2.");
            process.removeListener("SIGUSR2", handler);
            resolve();
        };

        // SIGUSR2 is available on POSIX systems but not identically on every
        // operating system.
        process.on("SIGUSR2", handler);

        try {
            process.kill(process.pid, "SIGUSR2");
        } catch (error) {
            process.removeListener("SIGUSR2", handler);
            console.log("Signal demonstration unavailable:", error.message);
            resolve();
        }
    });
}


// ---------------------------------------------------------------------------
// Graceful shutdown
// ---------------------------------------------------------------------------

function demonstrateGracefulShutdown() {
    heading("7. Graceful shutdown architecture");

    return new Promise(resolve => {
        let shuttingDown = false;

        const shutdown = reason => {
            if (shuttingDown) return;

            shuttingDown = true;
            console.log("Shutdown requested because of:", reason);

            // Real services should close servers, database connections,
            // queues, files, and other resources here.
            setTimeout(() => {
                console.log("Cleanup completed.");
                process.removeListener("SIGTERM", onSigterm);
                resolve();
            }, 50);
        };

        const onSigterm = () => shutdown("SIGTERM");

        process.once("SIGTERM", onSigterm);

        // Trigger the handler without terminating this educational program.
        process.kill(process.pid, "SIGTERM");
    });
}


// ---------------------------------------------------------------------------
// Worker threads
// ---------------------------------------------------------------------------

function runPrimeWorker(start, end) {
    return new Promise((resolve, reject) => {
        const worker = new Worker(__filename, {
            workerData: {
                type: "prime-count",
                start,
                end
            }
        });

        worker.once("message", resolve);

        worker.once("error", reject);

        worker.once("exit", code => {
            if (code !== 0) {
                reject(new Error(`Worker exited with code ${code}`));
            }
        });
    });
}

async function demonstrateWorkerThreads() {
    heading("8. Worker threads");

    const ranges = [
        [100000, 100500],
        [100500, 101000],
        [101000, 101500]
    ];

    const results = await Promise.all(
        ranges.map(([start, end]) => runPrimeWorker(start, end))
    );

    console.log("Worker results:", results);
    console.log(
        "Total primes:",
        results.reduce((total, result) => total + result.count, 0)
    );
}


// ---------------------------------------------------------------------------
// Fork and IPC
// ---------------------------------------------------------------------------

async function demonstrateForkIPC() {
    heading("9. IPC with child_process.fork");

    /*
     * A forked Node.js child can communicate using process.send()
     * and message events. This is process-level isolation, unlike
     * worker_threads which run inside the same OS process.
     */

    const childSource = `
        process.on("message", message => {
            if (message.type === "square") {
                process.send({
                    number: message.number,
                    square: message.number * message.number
                });
            }

            if (message.type === "shutdown") {
                process.exit(0);
            }
        });
    `;

    // fork() requires a JavaScript file, so write a temporary helper.
    const temporaryFile = path.join(
        os.tmpdir(),
        `node-ipc-worker-${process.pid}.js`
    );

    fs.writeFileSync(temporaryFile, childSource, "utf8");

    const child = fork(
        temporaryFile,
        [],
        {
            stdio: ["ignore", "ignore", "ignore", "ipc"]
        }
    );

    const results = [];

    child.on("message", message => {
        results.push(message);
    });

    for (const number of [2, 5, 9, 12]) {
        child.send({
            type: "square",
            number
        });
    }

    await sleep(100);

    child.send({ type: "shutdown" });

    await new Promise(resolve => {
        child.on("exit", resolve);
    });

    fs.unlinkSync(temporaryFile);

    console.log("IPC results:", results);
}


// ---------------------------------------------------------------------------
// Event loop distinction
// ---------------------------------------------------------------------------

async function demonstrateEventLoop() {
    heading("10. Event loop and asynchronous process APIs");

    const events = [];

    events.push("synchronous start");

    setTimeout(() => {
        events.push("timer callback");
        console.log("Event order:", events);
    }, 0);

    Promise.resolve().then(() => {
        events.push("microtask");
    });

    events.push("synchronous end");

    await sleep(20);
}


// ---------------------------------------------------------------------------
// Process table on Linux
// ---------------------------------------------------------------------------

function demonstrateLinuxProc() {
    heading("11. Linux /proc process inspection");

    if (process.platform !== "linux") {
        console.log("/proc is Linux-specific; section skipped.");
        return;
    }

    const entries = fs.readdirSync("/proc", {
        withFileTypes: true
    });

    const pids = entries
        .filter(entry => entry.isDirectory() && /^\d+$/.test(entry.name))
        .map(entry => Number(entry.name))
        .sort((a, b) => a - b)
        .slice(0, 15);

    for (const pid of pids) {
        try {
            const status = fs.readFileSync(
                `/proc/${pid}/status`,
                "utf8"
            );

            const name = status.match(/^Name:\s*(.+)$/m)?.[1] ?? "?";
            const state = status.match(/^State:\s*(.+)$/m)?.[1] ?? "?";
            const parent = status.match(/^PPid:\s*(\d+)$/m)?.[1] ?? "?";

            console.log(
                `PID=${pid.toString().padEnd(7)} ` +
                `PPID=${parent.padEnd(7)} ` +
                `STATE=${state.padEnd(25)} ` +
                `NAME=${name}`
            );
        } catch {
            // A process can disappear between enumeration and inspection.
        }
    }
}


// ---------------------------------------------------------------------------
// Service configuration model
// ---------------------------------------------------------------------------

class ServiceController {
    constructor(name) {
        this.name = name;
        this.running = false;
        this.startedAt = null;
    }

    start() {
        if (this.running) {
            throw new Error(`Service ${this.name} is already running`);
        }

        this.running = true;
        this.startedAt = new Date();
        console.log(`${this.name}: started`);
    }

    stop() {
        if (!this.running) {
            return;
        }

        this.running = false;
        console.log(`${this.name}: stopped`);
    }

    status() {
        return {
            name: this.name,
            active: this.running,
            startedAt: this.startedAt
                ? this.startedAt.toISOString()
                : null
        };
    }
}

function demonstrateServiceModel() {
    heading("12. Service lifecycle model");

    const service = new ServiceController("example-api");

    service.start();
    console.log(service.status());
    service.stop();
    console.log(service.status());
}


// ---------------------------------------------------------------------------
// systemd interaction
// ---------------------------------------------------------------------------

function demonstrateSystemd() {
    heading("13. systemd and systemctl");

    if (process.platform !== "linux") {
        console.log("systemd is primarily a Linux facility; section skipped.");
        return Promise.resolve();
    }

    return new Promise(resolve => {
        execFile(
            "systemctl",
            [
                "list-units",
                "--type=service",
                "--no-pager",
                "--no-legend"
            ],
            {
                encoding: "utf8",
                timeout: 5000
            },
            (error, stdout, stderr) => {
                if (error) {
                    console.log(
                        "systemctl query unavailable:",
                        error.message
                    );
                    if (stderr) console.log(stderr.trim());
                    resolve();
                    return;
                }

                const lines = stdout.split(/\r?\n/).filter(Boolean);

                console.log(
                    `Visible active service units: ${lines.length}`
                );

                for (const line of lines.slice(0, 5)) {
                    console.log(line);
                }

                resolve();
            }
        );
    });
}


// ---------------------------------------------------------------------------
// Security
// ---------------------------------------------------------------------------

async function demonstrateSecureExecution() {
    heading("14. Secure child-process execution");

    /*
     * Safe:
     *     execFile(executable, [argument1, argument2])
     *
     * Risky:
     *     exec(`command ${untrustedInput}`)
     *
     * The risky pattern can allow shell metacharacters to change the
     * meaning of the command. Prefer execFile() or spawn() with an
     * explicit argument array.
     */

    try {
        const result = await runExecFile(
            process.execPath,
            ["-e", "console.log(6 * 7)"]
        );

        console.log("Safe output:", result.stdout.trim());
    } catch (result) {
        console.error("Execution error:", result.error.message);
    }
}


// ---------------------------------------------------------------------------
// Failure handling
// ---------------------------------------------------------------------------

async function demonstrateFailureHandling() {
    heading("15. Failure conditions");

    try {
        await runExecFile(
            process.execPath,
            ["-e", "process.exit(42)"]
        );
    } catch (result) {
        console.log("Child failed as expected.");
        console.log("Return code:", result.error.code);
    }

    try {
        await runExecFile(
            "definitely-not-an-executable",
            []
        );
    } catch (result) {
        console.log(
            "Executable lookup failure handled:",
            result.error.code
        );
    }
}


// ---------------------------------------------------------------------------
// Process versus thread model
// ---------------------------------------------------------------------------

function demonstrateComparison() {
    heading("16. Process and thread characteristics");

    const comparison = [
        {
            concept: "Address space",
            process: "Separate",
            thread: "Shared within process"
        },
        {
            concept: "Failure isolation",
            process: "Higher",
            thread: "Lower"
        },
        {
            concept: "Communication",
            process: "IPC",
            thread: "Shared memory / messages"
        },
        {
            concept: "Startup cost",
            process: "Usually higher",
            thread: "Usually lower"
        },
        {
            concept: "OS scheduling",
            process: "Scheduled",
            thread: "Threads are scheduled"
        }
    ];

    console.table(comparison);
}


// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

function assert(condition, message) {
    if (!condition) {
        throw new Error(`Assertion failed: ${message}`);
    }
}

function runTests() {
    heading("17. Embedded tests");

    assert(process.pid > 0, "PID should be positive");
    assert(process.execPath.length > 0, "Executable should exist");
    assert(typeof process.cwd() === "string", "Working directory is a string");
    assert(os.cpus().length >= 1, "At least one logical CPU is expected");

    const service = new ServiceController("test-service");
    service.start();
    assert(service.status().active === true, "Service should be active");
    service.stop();
    assert(service.status().active === false, "Service should be inactive");

    console.log("All JavaScript tests passed.");
}


// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
    console.log("Processes and Services study program");
    console.log("Running PID:", process.pid);

    demonstrateProcessIdentity();
    demonstrateMemoryMetrics();

    await demonstrateChildProcess();
    await demonstrateSpawn();
    demonstrateLinuxProc();

    await demonstrateTimeout();
    await demonstrateSignals();
    await demonstrateGracefulShutdown();

    await demonstrateWorkerThreads();
    await demonstrateForkIPC();
    await demonstrateEventLoop();

    demonstrateServiceModel();
    await demonstrateSystemd();

    await demonstrateSecureExecution();
    await demonstrateFailureHandling();
    demonstrateComparison();

    runTests();

    console.log("\nStudy program completed.");
}

main().catch(error => {
    console.error("Fatal error:", error);
    process.exitCode = 1;
});
