#include <algorithm>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <regex>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>
#include <atomic>
#include <mutex>
#include <future>
#include <cstdlib>

namespace fs = std::filesystem;

// ---------------------------------------------------------------------------
// Shell scripting case study:
// Secure, idempotent deployment automation
//
// The program models the architecture of a production Bash deployment
// workflow:
//
//     validate -> prepare -> verify -> deploy -> health check
//                                      |
//                                      v
//                                   rollback
//
// C++ is used here to demonstrate how the same system can be represented
// with stronger types, explicit data structures, deterministic validation,
// concurrency control, and resource management.
// ---------------------------------------------------------------------------

void printSection(const std::string& title) {
    std::cout << "\n" << std::string(78, '=') << "\n";
    std::cout << title << "\n";
    std::cout << std::string(78, '=') << "\n";
}

void printSubsection(const std::string& title) {
    std::cout << "\n" << std::string(78, '-') << "\n";
    std::cout << title << "\n";
    std::cout << std::string(78, '-') << "\n";
}


// ---------------------------------------------------------------------------
// Basic shell concepts represented as C++ data
// ---------------------------------------------------------------------------

void demonstrateShellConcepts() {
    printSection("1. Shell scripting concepts represented in C++");

    std::cout
        << "A shell interprets commands and coordinates operating-system "
           "programs.\n"
        << "Bash commonly uses variables, conditions, loops, functions, "
           "arguments,\n"
        << "pipelines, redirection, exit statuses, and traps.\n\n";

    std::cout
        << "Typical Bash deployment sequence:\n"
        << "  1. Parse arguments\n"
        << "  2. Validate configuration\n"
        << "  3. Check dependencies\n"
        << "  4. Prepare filesystem resources\n"
        << "  5. Verify artifact\n"
        << "  6. Deploy\n"
        << "  7. Health check\n"
        << "  8. Roll back on failure\n";
}


// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

struct DeploymentConfig {
    std::string application;
    std::string version;
    std::string environment;
    fs::path releaseRoot;
    int retentionDays = 7;

    void validate() const {
        static const std::set<std::string> allowedEnvironments = {
            "development",
            "testing",
            "production"
        };

        if (!allowedEnvironments.contains(environment)) {
            throw std::invalid_argument(
                "Unsupported deployment environment: " + environment
            );
        }

        if (application.empty()) {
            throw std::invalid_argument(
                "Application name cannot be empty."
            );
        }

        if (version.empty()) {
            throw std::invalid_argument(
                "Version cannot be empty."
            );
        }

        if (retentionDays < 1) {
            throw std::invalid_argument(
                "Retention days must be positive."
            );
        }

        // This mirrors a shell-script security rule: do not allow arbitrary
        // shell metacharacters in values that are later used in paths or
        // command arguments.
        const std::regex safeIdentifier(
            R"(^[A-Za-z0-9._-]+$)"
        );

        if (!std::regex_match(application, safeIdentifier)) {
            throw std::invalid_argument(
                "Application name contains unsupported characters."
            );
        }

        if (!std::regex_match(version, safeIdentifier)) {
            throw std::invalid_argument(
                "Version contains unsupported characters."
            );
        }
    }
};


// ---------------------------------------------------------------------------
// Logging
// ---------------------------------------------------------------------------

class Logger {
private:
    mutable std::mutex mutex;

    std::string timestamp() const {
        const auto now =
            std::chrono::system_clock::now();

        const std::time_t currentTime =
            std::chrono::system_clock::to_time_t(now);

        std::tm localTime{};

#ifdef _WIN32
        localtime_s(&localTime, &currentTime);
#else
        localtime_r(&currentTime, &localTime);
#endif

        std::ostringstream stream;
        stream << std::put_time(
            &localTime,
            "%Y-%m-%d %H:%M:%S"
        );

        return stream.str();
    }

public:
    void info(const std::string& message) {
        write("INFO", message);
    }

    void warning(const std::string& message) {
        write("WARNING", message);
    }

    void error(const std::string& message) {
        write("ERROR", message);
    }

private:
    void write(
        const std::string& level,
        const std::string& message
    ) {
        std::lock_guard<std::mutex> lock(mutex);

        std::cout
            << timestamp()
            << " ["
            << level
            << "] "
            << message
            << '\n';
    }
};


// ---------------------------------------------------------------------------
// Command-line arguments
// ---------------------------------------------------------------------------

class ArgumentParser {
private:
    std::map<std::string, std::string> options;

public:
    void parse(int argc, char* argv[]) {
        for (int i = 1; i < argc; ++i) {
            std::string argument = argv[i];

            if (argument.rfind("--", 0) != 0) {
                throw std::invalid_argument(
                    "Arguments must use --name=value form."
                );
            }

            const std::size_t separator =
                argument.find('=');

            if (separator == std::string::npos) {
                throw std::invalid_argument(
                    "Option requires a value: " + argument
                );
            }

            std::string name =
                argument.substr(2, separator - 2);

            std::string value =
                argument.substr(separator + 1);

            if (name.empty() || value.empty()) {
                throw std::invalid_argument(
                    "Option name and value cannot be empty."
                );
            }

            options[name] = value;
        }
    }

    bool contains(const std::string& name) const {
        return options.contains(name);
    }

    std::string get(
        const std::string& name,
        const std::string& defaultValue = ""
    ) const {
        auto iterator = options.find(name);

        if (iterator == options.end()) {
            return defaultValue;
        }

        return iterator->second;
    }
};


// ---------------------------------------------------------------------------
// File utilities
// ---------------------------------------------------------------------------

class FileManager {
private:
    Logger& logger;

public:
    explicit FileManager(Logger& loggerReference)
        : logger(loggerReference) {}

    void createDirectory(const fs::path& directory) {
        // Equivalent in spirit to:
        //
        //     mkdir -p "$directory"
        //
        // create_directories is naturally idempotent.
        fs::create_directories(directory);

        logger.info(
            "Directory prepared: " + directory.string()
        );
    }

    void writeFile(
        const fs::path& file,
        const std::string& content
    ) {
        std::ofstream output(file);

        if (!output) {
            throw std::runtime_error(
                "Unable to create file: " + file.string()
            );
        }

        output << content;

        if (!output) {
            throw std::runtime_error(
                "Unable to write file: " + file.string()
            );
        }
    }

    std::string readFile(const fs::path& file) const {
        std::ifstream input(file);

        if (!input) {
            throw std::runtime_error(
                "Unable to read file: " + file.string()
            );
        }

        std::ostringstream buffer;
        buffer << input.rdbuf();

        return buffer.str();
    }

    bool exists(const fs::path& path) const {
        return fs::exists(path);
    }
};


// ---------------------------------------------------------------------------
// Artifact verification
// ---------------------------------------------------------------------------

class ArtifactVerifier {
public:
    static std::string simpleDigest(
        const std::string& content
    ) {
        // This is intentionally a demonstration digest, not a cryptographic
        // implementation. Production artifact verification should use a
        // standard cryptographic library and a trusted authenticity mechanism.
        std::hash<std::string> hasher;
        const std::size_t value = hasher(content);

        std::ostringstream output;
        output << std::hex << value;

        return output.str();
    }

    static bool verify(
        const std::string& content,
        const std::string& expectedDigest
    ) {
        return simpleDigest(content) == expectedDigest;
    }
};


// ---------------------------------------------------------------------------
// Health checks
// ---------------------------------------------------------------------------

struct HealthCheckResult {
    std::string name;
    bool passed;
    std::string detail;
};

class HealthChecker {
private:
    Logger& logger;

public:
    explicit HealthChecker(Logger& loggerReference)
        : logger(loggerReference) {}

    std::vector<HealthCheckResult> run(
        const DeploymentConfig& config
    ) {
        std::vector<HealthCheckResult> results;

        // A real implementation could invoke service managers, TCP probes,
        // HTTP checks, database checks, and application-specific diagnostics.
        //
        // The case study keeps those operations deterministic and local.

        results.push_back({
            "configuration",
            true,
            "Configuration is valid."
        });

        results.push_back({
            "release-directory",
            fs::exists(config.releaseRoot),
            "Release directory existence check."
        });

        results.push_back({
            "application-version",
            !config.version.empty(),
            "Version metadata is present."
        });

        for (const auto& result : results) {
            if (result.passed) {
                logger.info(
                    "Health check passed: " + result.name
                );
            } else {
                logger.error(
                    "Health check failed: " + result.name
                );
            }
        }

        return results;
    }
};


// ---------------------------------------------------------------------------
// Deployment state
// ---------------------------------------------------------------------------

struct DeploymentState {
    std::string previousVersion;
    std::string deployedVersion;
    bool deploymentActive = false;
};


// ---------------------------------------------------------------------------
// Deployment automation
// ---------------------------------------------------------------------------

class DeploymentAutomation {
private:
    DeploymentConfig config;
    DeploymentState state;
    Logger& logger;
    FileManager fileManager;
    HealthChecker healthChecker;

public:
    DeploymentAutomation(
        DeploymentConfig deploymentConfig,
        Logger& loggerReference
    )
        : config(std::move(deploymentConfig)),
          logger(loggerReference),
          fileManager(loggerReference),
          healthChecker(loggerReference) {}

    void validate() {
        config.validate();

        logger.info(
            "Configuration validated for " +
            config.application
        );
    }

    void prepare() {
        fileManager.createDirectory(config.releaseRoot);

        fs::path versionDirectory =
            config.releaseRoot / config.version;

        fileManager.createDirectory(versionDirectory);

        logger.info(
            "Release workspace prepared: " +
            versionDirectory.string()
        );
    }

    void verifyArtifact() {
        const std::string artifactContent =
            config.application + ":" + config.version;

        const std::string digest =
            ArtifactVerifier::simpleDigest(
                artifactContent
            );

        if (!ArtifactVerifier::verify(
                artifactContent,
                digest
            )) {
            throw std::runtime_error(
                "Artifact integrity verification failed."
            );
        }

        logger.info(
            "Artifact integrity verification passed. Digest=" +
            digest
        );
    }

    void deploy() {
        fs::path releaseDirectory =
            config.releaseRoot / config.version;

        fs::path metadataFile =
            releaseDirectory / "release.txt";

        fileManager.writeFile(
            metadataFile,
            "application=" + config.application + "\n" +
            "version=" + config.version + "\n" +
            "environment=" + config.environment + "\n"
        );

        state.deployedVersion = config.version;
        state.deploymentActive = true;

        logger.info(
            "Release deployed: " +
            config.application +
            " version " +
            config.version
        );
    }

    bool healthCheck() {
        const auto results =
            healthChecker.run(config);

        return std::all_of(
            results.begin(),
            results.end(),
            [](const HealthCheckResult& result) {
                return result.passed;
            }
        );
    }

    void rollback() {
        state.deployedVersion = state.previousVersion;
        state.deploymentActive = false;

        logger.warning(
            "Rollback completed to version " +
            state.previousVersion
        );
    }

    bool run(const std::string& previousVersion) {
        state.previousVersion = previousVersion;

        try {
            validate();
            prepare();
            verifyArtifact();
            deploy();

            if (!healthCheck()) {
                rollback();
                return false;
            }

            logger.info(
                "Deployment completed successfully."
            );

            return true;
        } catch (const std::exception& error) {
            logger.error(
                std::string("Deployment failed: ") +
                error.what()
            );

            if (state.deploymentActive) {
                rollback();
            }

            return false;
        }
    }

    const DeploymentState& getState() const {
        return state;
    }
};


// ---------------------------------------------------------------------------
// Retry mechanism
// ---------------------------------------------------------------------------

class RetryPolicy {
private:
    int maximumAttempts;
    std::chrono::milliseconds initialDelay;

public:
    RetryPolicy(
        int attempts,
        std::chrono::milliseconds delay
    )
        : maximumAttempts(attempts),
          initialDelay(delay) {
        if (maximumAttempts < 1) {
            throw std::invalid_argument(
                "Retry attempts must be positive."
            );
        }
    }

    template <typename Operation>
    bool execute(
        Operation operation,
        Logger& logger
    ) const {
        auto delay = initialDelay;

        for (int attempt = 1;
             attempt <= maximumAttempts;
             ++attempt) {

            if (operation(attempt)) {
                logger.info(
                    "Operation succeeded on attempt " +
                    std::to_string(attempt)
                );

                return true;
            }

            if (attempt < maximumAttempts) {
                logger.warning(
                    "Attempt " +
                    std::to_string(attempt) +
                    " failed; retrying."
                );

                std::this_thread::sleep_for(delay);

                delay *= 2;
            }
        }

        logger.error(
            "Operation failed after maximum attempts."
        );

        return false;
    }
};


// ---------------------------------------------------------------------------
// Bounded concurrency demonstration
// ---------------------------------------------------------------------------

class TaskExecutor {
private:
    std::size_t concurrencyLimit;

public:
    explicit TaskExecutor(std::size_t limit)
        : concurrencyLimit(limit) {
        if (concurrencyLimit == 0) {
            throw std::invalid_argument(
                "Concurrency limit must be greater than zero."
            );
        }
    }

    std::vector<std::future<std::string>> run(
        const std::vector<std::string>& tasks
    ) {
        std::vector<std::future<std::string>> futures;

        // This simple executor launches work in batches. A production system
        // may use a persistent thread pool to avoid repeated thread creation.
        for (std::size_t offset = 0;
             offset < tasks.size();
             offset += concurrencyLimit) {

            std::vector<std::future<std::string>> batch;

            const std::size_t end =
                std::min(
                    tasks.size(),
                    offset + concurrencyLimit
                );

            for (std::size_t index = offset;
                 index < end;
                 ++index) {

                batch.push_back(
                    std::async(
                        std::launch::async,
                        [task = tasks[index]] {
                            std::this_thread::sleep_for(
                                std::chrono::milliseconds(10)
                            );

                            return task + ": completed";
                        }
                    )
                );
            }

            for (auto& future : batch) {
                futures.push_back(
                    std::move(future)
                );
            }
        }

        return futures;
    }
};


// ---------------------------------------------------------------------------
// Idempotence demonstration
// ---------------------------------------------------------------------------

void demonstrateIdempotence(
    const fs::path& directory,
    Logger& logger
) {
    printSubsection("Idempotence");

    FileManager fileManager(logger);

    // Repeating this operation does not fail merely because the directory
    // already exists.
    for (int attempt = 1; attempt <= 3; ++attempt) {
        fileManager.createDirectory(directory);
        logger.info(
            "Idempotent operation repetition " +
            std::to_string(attempt)
        );
    }
}


// ---------------------------------------------------------------------------
// Argument validation demonstration
// ---------------------------------------------------------------------------

void demonstrateArgumentValidation() {
    printSubsection("Argument validation");

    const std::vector<int> ports = {
        0,
        22,
        443,
        65535,
        65536
    };

    for (int port : ports) {
        const bool valid =
            port >= 1 && port <= 65535;

        std::cout
            << "Port "
            << std::setw(5)
            << port
            << " valid="
            << std::boolalpha
            << valid
            << '\n';
    }
}


// ---------------------------------------------------------------------------
// Complexity discussion
// ---------------------------------------------------------------------------

void demonstrateComplexity() {
    printSubsection("Complexity considerations");

    std::cout
        << "Configuration lookup in std::map: O(log n)\n"
        << "Environment membership in std::set: O(log n)\n"
        << "Vector health-check scan: O(n)\n"
        << "Filesystem operations: dominated by operating-system and storage "
           "latency\n"
        << "Concurrent tasks: throughput depends on task duration and the "
           "concurrency limit\n";

    std::cout
        << "\nShell-specific implication:\n"
        << "Starting a separate process has operating-system overhead. "
           "A script that launches\n"
        << "one process per input record can become substantially slower "
           "than an in-process\n"
        << "implementation for large workloads.\n";
}


// ---------------------------------------------------------------------------
// Security discussion
// ---------------------------------------------------------------------------

void demonstrateSecurity() {
    printSubsection("Security considerations");

    std::cout
        << "Shell automation security rules:\n"
        << "  - Quote variable expansions.\n"
        << "  - Validate user-controlled values.\n"
        << "  - Avoid eval with untrusted data.\n"
        << "  - Prefer argument arrays.\n"
        << "  - Use -- before filenames where supported.\n"
        << "  - Do not put secrets in source code.\n"
        << "  - Do not expose secrets in logs.\n"
        << "  - Use least-privilege accounts.\n"
        << "  - Protect temporary files and directories.\n"
        << "  - Verify artifact authenticity, not merely accidental integrity.\n";

    std::cout
        << "\nC++ implementation principle:\n"
        << "The case study keeps external command execution out of the core "
           "deployment logic.\n"
        << "This separation makes the state transitions easier to validate "
           "and test.\n";
}


// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

int main(int argc, char* argv[]) {
    printSection(
        "Bash Shell Scripting: C++ Deployment Automation Case Study"
    );

    try {
        demonstrateShellConcepts();

        Logger logger;

        DeploymentConfig config{
            "inventory-api",
            "2026.09.19",
            "production",
            fs::temp_directory_path() /
                "shell-study-release",
            14
        };

        printSubsection("Deployment configuration");

        std::cout
            << "Application: "
            << config.application
            << '\n'
            << "Version: "
            << config.version
            << '\n'
            << "Environment: "
            << config.environment
            << '\n'
            << "Retention days: "
            << config.retentionDays
            << '\n';

        printSubsection("Deployment execution");

        DeploymentAutomation automation(
            config,
            logger
        );

        const bool success =
            automation.run("2026.09.18");

        const DeploymentState& state =
            automation.getState();

        std::cout
            << "\nDeployment success: "
            << std::boolalpha
            << success
            << '\n'
            << "Current deployed version: "
            << state.deployedVersion
            << '\n';

        demonstrateIdempotence(
            config.releaseRoot / "stable",
            logger
        );

        printSubsection("Retry policy");

        RetryPolicy retryPolicy(
            4,
            std::chrono::milliseconds(10)
        );

        int simulatedAttempts = 0;

        retryPolicy.execute(
            [&](int attempt) {
                simulatedAttempts = attempt;

                // Simulate a transient failure for the first two attempts.
                return attempt >= 3;
            },
            logger
        );

        std::cout
            << "Simulated attempts: "
            << simulatedAttempts
            << '\n';

        printSubsection("Bounded concurrency");

        std::vector<std::string> tasks = {
            "database-check",
            "cache-check",
            "filesystem-check",
            "api-check",
            "queue-check"
        };

        TaskExecutor executor(2);

        auto futures = executor.run(tasks);

        for (auto& future : futures) {
            std::cout
                << future.get()
                << '\n';
        }

        demonstrateArgumentValidation();
        demonstrateComplexity();
        demonstrateSecurity();

        printSubsection("Failure conditions handled by the case study");

        std::cout
            << "The implementation explicitly handles:\n"
            << "  - invalid environment values\n"
            << "  - empty application names\n"
            << "  - invalid identifiers\n"
            << "  - invalid retention periods\n"
            << "  - filesystem failures\n"
            << "  - artifact verification failures\n"
            << "  - failed health checks\n"
            << "  - rollback requirements\n"
            << "  - invalid concurrency limits\n"
            << "  - invalid retry configuration\n";

        // Cleanup is intentionally performed only on the demonstration
        // workspace created by this program.
        std::error_code cleanupError;

        fs::remove_all(
            config.releaseRoot,
            cleanupError
        );

        if (cleanupError) {
            logger.warning(
                "Cleanup reported an error: " +
                cleanupError.message()
            );
        } else {
            logger.info(
                "Demonstration workspace cleaned up."
            );
        }

        printSection("Case study completed");

        return success ? 0 : 1;
    }
    catch (const std::exception& error) {
        std::cerr
            << "Fatal error: "
            << error.what()
            << '\n';

        return 1;
    }
}
