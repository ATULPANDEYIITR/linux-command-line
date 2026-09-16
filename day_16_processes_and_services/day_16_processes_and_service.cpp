#include <algorithm>
#include <atomic>
#include <chrono>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <mutex>
#include <optional>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

#ifdef __linux__
#include <cerrno>
#include <sys/resource.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#endif

/*
 * Processes and Services
 * ======================
 *
 * Industry-style C++ case study:
 *
 * A lightweight Linux service supervisor monitors worker processes that
 * execute jobs. The program demonstrates:
 *
 * - Process identity
 * - fork/exec/wait
 * - parent-child relationships
 * - process states
 * - signals
 * - graceful shutdown
 * - process monitoring through /proc
 * - threads and synchronization
 * - IPC through pipes
 * - restart policies
 * - timeouts
 * - resource and priority considerations
 * - service-manager concepts
 *
 * Build:
 *
 *     g++ -std=c++17 -O2 -pthread processes_and_services.cpp -o process_service_demo
 *
 * The complete process-supervisor case study requires Linux/POSIX APIs.
 * The source still compiles on other systems because platform-specific
 * sections are guarded where appropriate.
 */

using namespace std::chrono_literals;


// ---------------------------------------------------------------------------
// General utilities
// ---------------------------------------------------------------------------

void printHeading(const std::string& title) {
    std::cout << "\n" << std::string(78, '=') << "\n";
    std::cout << title << "\n";
    std::cout << std::string(78, '=') << "\n";
}


struct ProcessInfo {
    int pid = 0;
    int parentPid = 0;
    std::string name;
    std::string state;
    std::string threads;
    std::string residentMemory;
};


#ifdef __linux__

// ---------------------------------------------------------------------------
// /proc inspection
// ---------------------------------------------------------------------------

std::map<std::string, std::string> readProcStatus(int pid) {
    std::map<std::string, std::string> fields;

    std::ifstream input("/proc/" + std::to_string(pid) + "/status");

    if (!input) {
        return fields;
    }

    std::string line;

    while (std::getline(input, line)) {
        const auto separator = line.find(':');

        if (separator == std::string::npos) {
            continue;
        }

        std::string key = line.substr(0, separator);
        std::string value = line.substr(separator + 1);

        while (!value.empty() &&
               (value.front() == ' ' || value.front() == '\t')) {
            value.erase(value.begin());
        }

        fields[key] = value;
    }

    return fields;
}


std::optional<ProcessInfo> inspectProcess(int pid) {
    const auto fields = readProcStatus(pid);

    if (fields.empty()) {
        return std::nullopt;
    }

    ProcessInfo info;
    info.pid = pid;
    info.name = fields.contains("Name") ? fields.at("Name") : "?";
    info.state = fields.contains("State") ? fields.at("State") : "?";
    info.threads = fields.contains("Threads") ? fields.at("Threads") : "?";
    info.residentMemory =
        fields.contains("VmRSS") ? fields.at("VmRSS") : "?";

    if (fields.contains("PPid")) {
        try {
            info.parentPid = std::stoi(fields.at("PPid"));
        } catch (...) {
            info.parentPid = 0;
        }
    }

    return info;
}


std::vector<int> listProcesses() {
    std::vector<int> pids;

    for (const auto& entry : std::filesystem::directory_iterator("/proc")) {
        if (!entry.is_directory()) {
            continue;
        }

        const std::string name = entry.path().filename().string();

        if (std::all_of(
                name.begin(),
                name.end(),
                [](unsigned char character) {
                    return std::isdigit(character);
                })) {
            try {
                pids.push_back(std::stoi(name));
            } catch (...) {
                // A /proc entry may disappear or contain an unexpected value.
            }
        }
    }

    std::sort(pids.begin(), pids.end());

    return pids;
}


void printProcessTable(std::size_t maximum = 15) {
    printHeading("1. Linux process table through /proc");

    const auto pids = listProcesses();

    std::size_t printed = 0;

    for (int pid : pids) {
        if (printed >= maximum) {
            break;
        }

        const auto info = inspectProcess(pid);

        if (!info) {
            continue;
        }

        std::cout
            << "PID=" << std::setw(7) << std::left << info->pid
            << " PPID=" << std::setw(7) << info->parentPid
            << " STATE=" << std::setw(25) << info->state
            << " THREADS=" << std::setw(5) << info->threads
            << " RSS=" << std::setw(12) << info->residentMemory
            << " NAME=" << info->name
            << "\n";

        ++printed;
    }
}


// ---------------------------------------------------------------------------
// Process identity
// ---------------------------------------------------------------------------

void demonstrateIdentity() {
    printHeading("2. Process identity");

    std::cout << "Current PID : " << ::getpid() << "\n";
    std::cout << "Parent PID  : " << ::getppid() << "\n";
    std::cout << "UID         : " << ::getuid() << "\n";
    std::cout << "GID         : " << ::getgid() << "\n";
}


// ---------------------------------------------------------------------------
// Pipes and IPC
// ---------------------------------------------------------------------------

class Pipe {
public:
    Pipe() {
        if (::pipe(fileDescriptors) == -1) {
            throw std::runtime_error(
                std::string("pipe() failed: ") + std::strerror(errno)
            );
        }
    }

    ~Pipe() {
        closeRead();
        closeWrite();
    }

    int readEnd() const {
        return fileDescriptors[0];
    }

    int writeEnd() const {
        return fileDescriptors[1];
    }

    void closeRead() {
        if (fileDescriptors[0] != -1) {
            ::close(fileDescriptors[0]);
            fileDescriptors[0] = -1;
        }
    }

    void closeWrite() {
        if (fileDescriptors[1] != -1) {
            ::close(fileDescriptors[1]);
            fileDescriptors[1] = -1;
        }
    }

private:
    int fileDescriptors[2]{-1, -1};
};


void demonstratePipeIPC() {
    printHeading("3. Parent-child IPC using a pipe");

    Pipe pipe;

    const pid_t child = ::fork();

    if (child == -1) {
        throw std::runtime_error(
            std::string("fork() failed: ") + std::strerror(errno)
        );
    }

    if (child == 0) {
        // Child does not need the read side.
        pipe.closeRead();

        const std::string message =
            "worker process " +
            std::to_string(::getpid()) +
            " completed its IPC task\n";

        const ssize_t bytesWritten = ::write(
            pipe.writeEnd(),
            message.data(),
            message.size()
        );

        pipe.closeWrite();

        // _exit avoids flushing inherited parent-side C stdio buffers.
        _exit(bytesWritten == static_cast<ssize_t>(message.size()) ? 0 : 1);
    }

    // Parent does not need the write side.
    pipe.closeWrite();

    char buffer[256]{};
    const ssize_t bytesRead =
        ::read(pipe.readEnd(), buffer, sizeof(buffer) - 1);

    pipe.closeRead();

    int status = 0;

    if (::waitpid(child, &status, 0) == -1) {
        throw std::runtime_error(
            std::string("waitpid() failed: ") + std::strerror(errno)
        );
    }

    if (bytesRead > 0) {
        buffer[bytesRead] = '\0';
        std::cout << "Parent received: " << buffer;
    }

    if (WIFEXITED(status)) {
        std::cout << "Child exit code: " << WEXITSTATUS(status) << "\n";
    }
}


// ---------------------------------------------------------------------------
// CPU work
// ---------------------------------------------------------------------------

bool isPrime(std::uint64_t number) {
    if (number < 2) {
        return false;
    }

    if (number == 2) {
        return true;
    }

    if (number % 2 == 0) {
        return false;
    }

    for (std::uint64_t divisor = 3;
         divisor * divisor <= number;
         divisor += 2) {

        if (number % divisor == 0) {
            return false;
        }
    }

    return true;
}


std::uint64_t countPrimes(
    std::uint64_t start,
    std::uint64_t end
) {
    std::uint64_t count = 0;

    for (std::uint64_t number = start; number < end; ++number) {
        if (isPrime(number)) {
            ++count;
        }
    }

    return count;
}


void demonstrateThreads() {
    printHeading("4. Threads and shared memory");

    std::atomic<std::uint64_t> total{0};

    const unsigned int workerCount =
        std::max(1u, std::thread::hardware_concurrency());

    std::vector<std::thread> workers;

    for (unsigned int worker = 0; worker < workerCount; ++worker) {
        workers.emplace_back([&total, worker]() {
            for (int iteration = 0; iteration < 10000; ++iteration) {
                total.fetch_add(1, std::memory_order_relaxed);
            }

            std::cout
                << "Thread " << worker
                << " completed on thread ID "
                << std::this_thread::get_id()
                << "\n";
        });
    }

    for (auto& worker : workers) {
        worker.join();
    }

    std::cout << "Expected increments: "
              << static_cast<std::uint64_t>(workerCount) * 10000
              << "\n";

    std::cout << "Actual increments: "
              << total.load()
              << "\n";
}


// ---------------------------------------------------------------------------
// Signals
// ---------------------------------------------------------------------------

std::atomic<bool> shutdownRequested{false};


void signalHandler(int signalNumber) {
    /*
     * Signal handlers have strict safety rules. In production code, avoid
     * complex operations, allocation, locks, and most library calls inside
     * the handler. A flag of type sig_atomic_t or an appropriate atomic
     * strategy can communicate the request to normal application code.
     */
    if (signalNumber == SIGTERM || signalNumber == SIGINT) {
        shutdownRequested.store(true);
    }
}


void installSignalHandlers() {
    struct sigaction action {};
    action.sa_handler = signalHandler;
    sigemptyset(&action.sa_mask);
    action.sa_flags = 0;

    if (::sigaction(SIGTERM, &action, nullptr) == -1) {
        throw std::runtime_error("Unable to install SIGTERM handler");
    }

    if (::sigaction(SIGINT, &action, nullptr) == -1) {
        throw std::runtime_error("Unable to install SIGINT handler");
    }
}


// ---------------------------------------------------------------------------
// Service-style worker
// ---------------------------------------------------------------------------

class JobService {
public:
    explicit JobService(std::string serviceName)
        : name(std::move(serviceName)) {}

    void start() {
        if (running.load()) {
            throw std::runtime_error("Service already running");
        }

        running.store(true);

        worker = std::thread([this]() {
            run();
        });
    }

    void stop() {
        running.store(false);

        if (worker.joinable()) {
            worker.join();
        }
    }

    bool isRunning() const {
        return running.load();
    }

private:
    void run() {
        std::cout << name << ": worker started\n";

        while (running.load()) {
            /*
             * A real service could consume messages, process jobs,
             * communicate with a database, expose an API, or perform
             * scheduled work here.
             */
            std::this_thread::sleep_for(50ms);
        }

        std::cout << name << ": worker performing cleanup\n";
        std::cout << name << ": worker stopped\n";
    }

    std::string name;
    std::atomic<bool> running{false};
    std::thread worker;
};


void demonstrateServiceLifecycle() {
    printHeading("5. Application service lifecycle");

    JobService service("analytics-worker");

    service.start();

    std::this_thread::sleep_for(150ms);

    std::cout << "Service active: "
              << std::boolalpha
              << service.isRunning()
              << "\n";

    service.stop();

    std::cout << "Service active after stop: "
              << service.isRunning()
              << "\n";
}


// ---------------------------------------------------------------------------
// Process supervisor
// ---------------------------------------------------------------------------

struct ChildResult {
    pid_t pid = -1;
    int exitCode = -1;
    bool exitedNormally = false;
    bool terminatedBySignal = false;
    int signalNumber = 0;
};


class ProcessSupervisor {
public:
    explicit ProcessSupervisor(std::string executable)
        : executable(std::move(executable)) {}

    ChildResult runChild() {
        const pid_t child = ::fork();

        if (child == -1) {
            throw std::runtime_error(
                std::string("fork() failed: ") + std::strerror(errno)
            );
        }

        if (child == 0) {
            /*
             * execl replaces the child process image with the requested
             * executable. The original parent remains independent.
             */
            ::execl(
                executable.c_str(),
                executable.c_str(),
                static_cast<char*>(nullptr)
            );

            // Reached only when exec fails.
            _exit(127);
        }

        int status = 0;

        if (::waitpid(child, &status, 0) == -1) {
            throw std::runtime_error(
                std::string("waitpid() failed: ") + std::strerror(errno)
            );
        }

        ChildResult result;
        result.pid = child;

        if (WIFEXITED(status)) {
            result.exitedNormally = true;
            result.exitCode = WEXITSTATUS(status);
        }

        if (WIFSIGNALED(status)) {
            result.terminatedBySignal = true;
            result.signalNumber = WTERMSIG(status);
        }

        return result;
    }

private:
    std::string executable;
};


void demonstrateSupervisor() {
    printHeading("6. Process supervisor using fork/exec/wait");

    ProcessSupervisor supervisor("/bin/sh");

    const ChildResult result = supervisor.runChild();

    std::cout << "Child PID: " << result.pid << "\n";

    if (result.exitedNormally) {
        std::cout << "Normal exit code: "
                  << result.exitCode
                  << "\n";
    }

    if (result.terminatedBySignal) {
        std::cout << "Child terminated by signal: "
                  << result.signalNumber
                  << "\n";
    }
}


// ---------------------------------------------------------------------------
// Priority and scheduling
// ---------------------------------------------------------------------------

void demonstratePriority() {
    printHeading("7. Process priority");

    errno = 0;

    const int priority = ::getpriority(PRIO_PROCESS, 0);

    if (errno != 0) {
        std::cerr
            << "getpriority failed: "
            << std::strerror(errno)
            << "\n";
        return;
    }

    std::cout << "Current nice value: " << priority << "\n";

    /*
     * Increasing the nice value generally lowers CPU scheduling priority.
     * Decreasing it can require elevated privileges. Resource policies
     * should be established deliberately rather than changed casually.
     */
}


// ---------------------------------------------------------------------------
// Monitoring a specific process
// ---------------------------------------------------------------------------

void demonstrateSelfMonitoring() {
    printHeading("8. Monitoring the current process");

    const int pid = static_cast<int>(::getpid());

    for (int sample = 0; sample < 3; ++sample) {
        const auto info = inspectProcess(pid);

        if (info) {
            std::cout
                << "Sample " << sample + 1
                << ": PID=" << info->pid
                << ", state=" << info->state
                << ", threads=" << info->threads
                << ", RSS=" << info->residentMemory
                << "\n";
        }

        std::this_thread::sleep_for(100ms);
    }
}


// ---------------------------------------------------------------------------
// Signal-driven service loop
// ---------------------------------------------------------------------------

void demonstrateSignalDrivenLoop() {
    printHeading("9. Signal-driven graceful shutdown");

    shutdownRequested.store(false);

    /*
     * For an interactive demonstration we send SIGTERM to ourselves after
     * a short delay. A production service would normally receive SIGTERM
     * from systemd, a container runtime, an administrator, or another
     * supervising process.
     */
    std::thread signalSender([]() {
        std::this_thread::sleep_for(150ms);
        ::kill(::getpid(), SIGTERM);
    });

    int iterations = 0;

    while (!shutdownRequested.load()) {
        ++iterations;
        std::this_thread::sleep_for(25ms);
    }

    signalSender.join();

    std::cout
        << "Shutdown request observed after "
        << iterations
        << " iterations.\n";

    std::cout << "Normal cleanup can now occur outside the signal handler.\n";
}


// ---------------------------------------------------------------------------
// systemd concepts
// ---------------------------------------------------------------------------

void demonstrateSystemdConcepts() {
    printHeading("10. systemd integration concepts");

    std::cout
        << "A systemd-managed service commonly has:\n"
        << "  - a unit definition\n"
        << "  - an executable or service command\n"
        << "  - dependency relationships\n"
        << "  - restart policy\n"
        << "  - environment configuration\n"
        << "  - resource controls\n"
        << "  - logging through the journal\n"
        << "  - lifecycle states such as active and failed\n\n";

    std::cout
        << "Typical read-only inspection commands include:\n"
        << "  systemctl status <unit>\n"
        << "  systemctl list-units --type=service\n"
        << "  systemctl is-active <unit>\n"
        << "  journalctl -u <unit>\n\n";

    std::cout
        << "Starting, stopping, enabling, or modifying services can require\n"
        << "appropriate privileges and should be treated as administrative\n"
        << "operations.\n";
}


// ---------------------------------------------------------------------------
// Error handling
// ---------------------------------------------------------------------------

class ServiceError : public std::runtime_error {
public:
    explicit ServiceError(const std::string& message)
        : std::runtime_error(message) {}
};


void demonstrateErrorHandling() {
    printHeading("11. Error handling");

    try {
        const auto info = inspectProcess(-1);

        if (!info) {
            throw ServiceError(
                "Process -1 could not be inspected"
            );
        }
    } catch (const ServiceError& error) {
        std::cout
            << "Handled service error: "
            << error.what()
            << "\n";
    }
}


// ---------------------------------------------------------------------------
// Security model
// ---------------------------------------------------------------------------

void demonstrateSecurityPrinciples() {
    printHeading("12. Process security considerations");

    const std::vector<std::string> principles = {
        "Run services with the minimum required privileges.",
        "Avoid executing shell commands with untrusted input.",
        "Validate configuration before starting workers.",
        "Use absolute executable paths when appropriate.",
        "Restrict filesystem and device access.",
        "Treat environment variables as untrusted configuration.",
        "Do not expose sensitive command-line arguments unnecessarily.",
        "Use resource limits to reduce denial-of-service impact.",
        "Audit service logs without leaking secrets.",
        "Use systemd sandboxing and account isolation where appropriate."
    };

    for (const auto& principle : principles) {
        std::cout << "- " << principle << "\n";
    }
}


// ---------------------------------------------------------------------------
// Complexity discussion
// ---------------------------------------------------------------------------

void demonstrateComplexity() {
    printHeading("13. Algorithmic and operational complexity");

    std::cout
        << "Prime testing in this program is approximately O(sqrt(n)) per\n"
        << "candidate using trial division.\n\n";

    std::cout
        << "Enumerating /proc is approximately O(P), where P is the number\n"
        << "of visible process-directory entries. Reading each status file\n"
        << "adds operating-system I/O overhead.\n\n";

    std::cout
        << "Thread creation and process creation have implementation-dependent\n"
        << "costs. Process creation generally involves more isolation and OS\n"
        << "state than creating a thread.\n";
}


// ---------------------------------------------------------------------------
// Embedded tests
// ---------------------------------------------------------------------------

void require(bool condition, const std::string& message) {
    if (!condition) {
        throw std::runtime_error("Test failure: " + message);
    }
}


void runTests() {
    printHeading("14. Embedded tests");

    require(isPrime(2), "2 must be prime");
    require(isPrime(97), "97 must be prime");
    require(!isPrime(1), "1 must not be prime");
    require(!isPrime(100), "100 must not be prime");
    require(countPrimes(2, 11) == 4, "primes below 11 are 2,3,5,7");

    const auto self = inspectProcess(static_cast<int>(::getpid()));

    require(self.has_value(), "Current process should be visible in /proc");
    require(self->pid == static_cast<int>(::getpid()),
            "Self PID must match");

    std::cout << "All C++ tests passed.\n";
}


// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

int main() {
    try {
        std::cout
            << "Processes and Services: C++ technical case study\n"
            << "PID: " << ::getpid() << "\n";

        installSignalHandlers();

        demonstrateIdentity();
        printProcessTable();
        demonstratePipeIPC();
        demonstrateThreads();
        demonstrateServiceLifecycle();
        demonstrateSupervisor();
        demonstratePriority();
        demonstrateSelfMonitoring();
        demonstrateSignalDrivenLoop();
        demonstrateSystemdConcepts();
        demonstrateErrorHandling();
        demonstrateSecurityPrinciples();
        demonstrateComplexity();
        runTests();

        printHeading("Case study complete");

        return 0;
    } catch (const std::exception& error) {
        std::cerr
            << "Fatal error: "
            << error.what()
            << "\n";

        return 1;
    }
}

#else

int main() {
    std::cout
        << "This technical case study requires Linux/POSIX APIs such as "
        << "fork(), exec(), waitpid(), signals, and /proc.\n"
        << "Compile this program on a Linux system for the complete "
        << "process-supervisor implementation.\n";

    return 0;
}

#endif
