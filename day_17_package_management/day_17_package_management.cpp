#include <algorithm>
#include <cstdint>
#include <functional>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

/*
 * PACKAGE MANAGEMENT CASE STUDY
 *
 * Scenario:
 *   A company operates a modular analytics platform composed of multiple
 *   services. The platform depends on shared libraries distributed through
 *   internal and external repositories.
 *
 * The program models a package manager that:
 *   - stores packages in repositories
 *   - compares semantic versions
 *   - interprets version constraints
 *   - resolves dependency graphs
 *   - detects dependency conflicts
 *   - verifies package integrity using a deterministic hash model
 *   - installs packages transactionally
 *   - creates a lock file
 *   - performs upgrades
 *   - maintains an artifact cache
 *   - checks whether removal is safe
 *   - reports dependency graphs and complexity
 *
 * Compile:
 *   g++ -std=c++17 -O2 package_management.cpp -o package_management
 *
 * The program uses only the C++17 standard library.
 */

// ============================================================================
// 1. UTILITY FUNCTIONS
// ============================================================================

void printSection(const std::string& title) {
    std::cout << "\n" << std::string(78, '=') << "\n";
    std::cout << title << "\n";
    std::cout << std::string(78, '=') << "\n";
}

// ============================================================================
// 2. SEMANTIC VERSION
// ============================================================================

struct Version {
    int major = 0;
    int minor = 0;
    int patch = 0;

    static Version parse(const std::string& text) {
        std::stringstream stream(text);
        Version result;
        char firstDot = '\0';
        char secondDot = '\0';

        if (!(stream >> result.major >> firstDot
                    >> result.minor >> secondDot
                    >> result.patch) ||
            firstDot != '.' ||
            secondDot != '.') {
            throw std::invalid_argument(
                "Invalid semantic version: " + text
            );
        }

        if (result.major < 0 ||
            result.minor < 0 ||
            result.patch < 0) {
            throw std::invalid_argument(
                "Version components cannot be negative."
            );
        }

        return result;
    }

    std::string toString() const {
        return std::to_string(major) + "." +
               std::to_string(minor) + "." +
               std::to_string(patch);
    }
};

bool operator==(const Version& left, const Version& right) {
    return left.major == right.major &&
           left.minor == right.minor &&
           left.patch == right.patch;
}

bool operator!=(const Version& left, const Version& right) {
    return !(left == right);
}

bool operator<(const Version& left, const Version& right) {
    if (left.major != right.major) {
        return left.major < right.major;
    }

    if (left.minor != right.minor) {
        return left.minor < right.minor;
    }

    return left.patch < right.patch;
}

bool operator>(const Version& left, const Version& right) {
    return right < left;
}

bool operator<=(const Version& left, const Version& right) {
    return !(right < left);
}

bool operator>=(const Version& left, const Version& right) {
    return !(left < right);
}

// ============================================================================
// 3. VERSION CONSTRAINT
// ============================================================================

class VersionConstraint {
private:
    std::string expression;

public:
    explicit VersionConstraint(std::string expression = "*")
        : expression(std::move(expression)) {}

    const std::string& text() const {
        return expression;
    }

    bool matches(const Version& version) const {
        if (expression.empty() || expression == "*") {
            return true;
        }

        if (expression.front() == '^') {
            Version base =
                Version::parse(expression.substr(1));

            Version upper;

            if (base.major > 0) {
                upper = {base.major + 1, 0, 0};
            } else if (base.minor > 0) {
                upper = {0, base.minor + 1, 0};
            } else {
                upper = {0, 0, base.patch + 1};
            }

            return version >= base && version < upper;
        }

        if (expression.front() == '~') {
            Version base =
                Version::parse(expression.substr(1));

            Version upper = {
                base.major,
                base.minor + 1,
                0
            };

            return version >= base && version < upper;
        }

        const std::vector<std::string> operators = {
            ">=", "<=", "==", ">", "<"
        };

        for (const std::string& operation : operators) {
            if (expression.rfind(operation, 0) == 0) {
                Version target =
                    Version::parse(
                        expression.substr(operation.size())
                    );

                if (operation == ">=") {
                    return version >= target;
                }

                if (operation == "<=") {
                    return version <= target;
                }

                if (operation == "==") {
                    return version == target;
                }

                if (operation == ">") {
                    return version > target;
                }

                if (operation == "<") {
                    return version < target;
                }
            }
        }

        // In this simplified model, a bare version means exact equality.
        return version == Version::parse(expression);
    }
};

// ============================================================================
// 4. DEPENDENCY
// ============================================================================

struct Dependency {
    std::string name;
    VersionConstraint constraint;

    Dependency(
        std::string name,
        VersionConstraint constraint
    )
        : name(std::move(name)),
          constraint(std::move(constraint)) {}
};

// ============================================================================
// 5. PACKAGE
// ============================================================================

struct Package {
    std::string name;
    Version version;
    std::vector<Dependency> dependencies;
    std::size_t sizeKB = 0;
    std::string description;
    std::string platform = "any";
    std::string checksum;

    std::string artifactContent() const {
        std::ostringstream output;

        output << name << "|"
               << version.toString() << "|";

        for (const auto& dependency : dependencies) {
            output << dependency.name
                   << ":"
                   << dependency.constraint.text()
                   << ",";
        }

        output << "|" << platform;

        return output.str();
    }

    std::string calculateChecksum() const {
        /*
         * This is a deterministic demonstration hash, not a cryptographic
         * implementation. Production package managers should use established
         * cryptographic hash algorithms and, where appropriate, signatures.
         */
        std::uint64_t hash =
            1469598103934665603ULL;

        const std::string content =
            artifactContent();

        for (unsigned char character : content) {
            hash ^= character;
            hash *= 1099511628211ULL;
        }

        std::ostringstream result;
        result << std::hex
               << std::setw(16)
               << std::setfill('0')
               << hash;

        return result.str();
    }

    void finalizeIntegrity() {
        checksum = calculateChecksum();
    }
};

// ============================================================================
// 6. REPOSITORY
// ============================================================================

class Repository {
private:
    std::string repositoryName;
    bool trusted;
    std::map<std::string, std::vector<Package>> packages;

public:
    Repository(
        std::string name,
        bool trusted = true
    )
        : repositoryName(std::move(name)),
          trusted(trusted) {}

    const std::string& name() const {
        return repositoryName;
    }

    bool isTrusted() const {
        return trusted;
    }

    void publish(Package package) {
        package.finalizeIntegrity();

        auto& versions = packages[package.name];

        versions.erase(
            std::remove_if(
                versions.begin(),
                versions.end(),
                [&](const Package& existing) {
                    return existing.version == package.version;
                }
            ),
            versions.end()
        );

        versions.push_back(std::move(package));

        std::sort(
            versions.begin(),
            versions.end(),
            [](const Package& left, const Package& right) {
                return left.version < right.version;
            }
        );
    }

    std::vector<Package> candidates(
        const std::string& packageName,
        const VersionConstraint& constraint
    ) const {
        std::vector<Package> result;

        auto iterator =
            packages.find(packageName);

        if (iterator == packages.end()) {
            return result;
        }

        for (const Package& package : iterator->second) {
            if (constraint.matches(package.version)) {
                result.push_back(package);
            }
        }

        return result;
    }

    std::optional<Package> exact(
        const std::string& packageName,
        const Version& version
    ) const {
        auto iterator =
            packages.find(packageName);

        if (iterator == packages.end()) {
            return std::nullopt;
        }

        for (const Package& package : iterator->second) {
            if (package.version == version) {
                return package;
            }
        }

        return std::nullopt;
    }

    void printContents() const {
        for (const auto& [name, versions] : packages) {
            std::cout << "  " << name << ": ";

            for (std::size_t index = 0;
                 index < versions.size();
                 ++index) {
                if (index > 0) {
                    std::cout << ", ";
                }

                std::cout
                    << versions[index].version.toString();
            }

            std::cout << "\n";
        }
    }
};

// ============================================================================
// 7. DEPENDENCY RESOLUTION
// ============================================================================

class ResolutionError : public std::runtime_error {
public:
    explicit ResolutionError(
        const std::string& message
    )
        : std::runtime_error(message) {}
};

struct Requirement {
    std::string name;
    VersionConstraint constraint;
    std::string requestedBy;
};

class DependencyResolver {
private:
    const std::vector<Repository>& repositories;

    std::vector<Package> candidates(
        const std::string& name,
        const VersionConstraint& constraint
    ) const {
        std::vector<Package> result;

        for (const Repository& repository : repositories) {
            if (!repository.isTrusted()) {
                continue;
            }

            std::vector<Package> repositoryCandidates =
                repository.candidates(name, constraint);

            result.insert(
                result.end(),
                repositoryCandidates.begin(),
                repositoryCandidates.end()
            );
        }

        // Newest candidates are considered first.
        std::sort(
            result.begin(),
            result.end(),
            [](const Package& left, const Package& right) {
                return left.version > right.version;
            }
        );

        return result;
    }

    std::map<std::string, Package> search(
        std::vector<Requirement> requirements,
        std::map<std::string, Package> selected
    ) const {
        if (requirements.empty()) {
            return selected;
        }

        Requirement current =
            requirements.front();

        requirements.erase(
            requirements.begin()
        );

        auto alreadySelected =
            selected.find(current.name);

        if (alreadySelected != selected.end()) {
            if (current.constraint.matches(
                    alreadySelected->second.version)) {
                return search(
                    requirements,
                    std::move(selected)
                );
            }

            throw ResolutionError(
                current.requestedBy +
                " requires " +
                current.name +
                " " +
                current.constraint.text() +
                ", but " +
                alreadySelected->second.version.toString() +
                " is already selected."
            );
        }

        std::vector<Package> available =
            candidates(
                current.name,
                current.constraint
            );

        if (available.empty()) {
            throw ResolutionError(
                "No package satisfies " +
                current.name +
                " " +
                current.constraint.text()
            );
        }

        for (const Package& candidate : available) {
            std::map<std::string, Package>
                nextSelected = selected;

            nextSelected[candidate.name] =
                candidate;

            std::vector<Requirement>
                nextRequirements = requirements;

            for (const Dependency& dependency :
                 candidate.dependencies) {
                nextRequirements.push_back({
                    dependency.name,
                    dependency.constraint,
                    candidate.name
                });
            }

            try {
                return search(
                    std::move(nextRequirements),
                    std::move(nextSelected)
                );
            } catch (const ResolutionError&) {
                /*
                 * Backtracking is required when the newest candidate is
                 * locally valid but incompatible with another branch.
                 */
            }
        }

        throw ResolutionError(
            "Dependency graph could not be resolved for " +
            current.name
        );
    }

public:
    explicit DependencyResolver(
        const std::vector<Repository>& repositories
    )
        : repositories(repositories) {}

    std::map<std::string, Package> resolve(
        const std::string& rootName,
        const VersionConstraint& rootConstraint
    ) const {
        return search(
            {
                {
                    rootName,
                    rootConstraint,
                    "root"
                }
            },
            {}
        );
    }
};

// ============================================================================
// 8. CACHE
// ============================================================================

class ArtifactCache {
private:
    std::map<
        std::pair<std::string, std::string>,
        Package
    > items;

public:
    bool contains(
        const std::string& name,
        const Version& version
    ) const {
        return items.find(
            {name, version.toString()}
        ) != items.end();
    }

    void put(const Package& package) {
        items[
            {package.name, package.version.toString()}
        ] = package;
    }

    std::optional<Package> get(
        const std::string& name,
        const Version& version
    ) const {
        auto iterator =
            items.find(
                {name, version.toString()}
            );

        if (iterator == items.end()) {
            return std::nullopt;
        }

        return iterator->second;
    }
};

// ============================================================================
// 9. LOCK FILE
// ============================================================================

struct LockEntry {
    std::string name;
    Version version;
    std::string checksum;
};

class LockFile {
private:
    std::map<std::string, LockEntry> entries;

public:
    void record(const Package& package) {
        entries[package.name] = {
            package.name,
            package.version,
            package.checksum
        };
    }

    void remove(const std::string& name) {
        entries.erase(name);
    }

    const std::map<std::string, LockEntry>&
    all() const {
        return entries;
    }

    void print() const {
        for (const auto& [name, entry] : entries) {
            std::cout
                << "  "
                << name
                << "@"
                << entry.version.toString()
                << " checksum="
                << entry.checksum
                << "\n";
        }
    }
};

// ============================================================================
// 10. PACKAGE MANAGER
// ============================================================================

class PackageManager {
private:
    const std::vector<Repository>& repositories;
    std::map<std::string, Package> installed;
    ArtifactCache cache;
    LockFile lockFile;
    std::vector<std::string> history;

    void verifyPackage(
        const Package& package
    ) const {
        if (package.checksum !=
            package.calculateChecksum()) {
            throw std::runtime_error(
                "Integrity verification failed for " +
                package.name
            );
        }
    }

public:
    explicit PackageManager(
        const std::vector<Repository>& repositories
    )
        : repositories(repositories) {}

    void install(
        const std::string& name,
        const VersionConstraint& constraint
    ) {
        std::cout
            << "\nInstalling "
            << name
            << " "
            << constraint.text()
            << "\n";

        /*
         * Transaction design:
         * resolve and verify everything before changing installed state.
         * If anything fails, the previous state remains intact.
         */
        std::map<std::string, Package>
            previousState = installed;

        try {
            DependencyResolver resolver(
                repositories
            );

            std::map<std::string, Package>
                resolved = resolver.resolve(
                    name,
                    constraint
                );

            for (const auto& [packageName, package] :
                 resolved) {
                verifyPackage(package);

                if (!cache.contains(
                        package.name,
                        package.version)) {
                    cache.put(package);
                }
            }

            for (const auto& [packageName, package] :
                 resolved) {
                installed[packageName] = package;
                lockFile.record(package);

                std::cout
                    << "  selected "
                    << package.name
                    << "@"
                    << package.version.toString()
                    << "\n";
            }

            history.push_back(
                "install " +
                name +
                " " +
                constraint.text()
            );
        } catch (...) {
            installed = std::move(previousState);
            throw;
        }
    }

    void remove(
        const std::string& name
    ) {
        std::cout
            << "\nRemoving "
            << name
            << "\n";

        auto target = installed.find(name);

        if (target == installed.end()) {
            std::cout
                << "  package is not installed\n";
            return;
        }

        std::vector<std::string>
            dependents;

        for (const auto& [packageName, package] :
             installed) {
            if (packageName == name) {
                continue;
            }

            for (const Dependency& dependency :
                 package.dependencies) {
                if (dependency.name == name) {
                    dependents.push_back(packageName);
                    break;
                }
            }
        }

        if (!dependents.empty()) {
            std::ostringstream message;

            message
                << "Cannot remove "
                << name
                << "; required by ";

            for (std::size_t index = 0;
                 index < dependents.size();
                 ++index) {
                if (index > 0) {
                    message << ", ";
                }

                message << dependents[index];
            }

            throw std::runtime_error(
                message.str()
            );
        }

        installed.erase(target);
        lockFile.remove(name);

        history.push_back(
            "remove " + name
        );

        std::cout
            << "  removed "
            << name
            << "\n";
    }

    void upgradeAll() {
        std::cout
            << "\nChecking for upgrades\n";

        std::vector<
            std::pair<Package, Package>
        > upgrades;

        for (const auto& [name, installedPackage] :
             installed) {
            std::vector<Package>
                candidates;

            for (const Repository& repository :
                 repositories) {
                std::vector<Package>
                    repositoryCandidates =
                    repository.candidates(
                        name,
                        VersionConstraint("*")
                    );

                candidates.insert(
                    candidates.end(),
                    repositoryCandidates.begin(),
                    repositoryCandidates.end()
                );
            }

            if (candidates.empty()) {
                continue;
            }

            auto newest =
                std::max_element(
                    candidates.begin(),
                    candidates.end(),
                    [](const Package& left,
                       const Package& right) {
                        return left.version <
                               right.version;
                    }
                );

            if (newest->version >
                installedPackage.version) {
                upgrades.push_back(
                    {installedPackage, *newest}
                );
            }
        }

        if (upgrades.empty()) {
            std::cout
                << "  no upgrades available\n";
            return;
        }

        /*
         * A production manager should re-resolve the complete graph for each
         * upgrade. This demonstration focuses on the update mechanism itself.
         */
        for (const auto& [oldPackage, newPackage] :
             upgrades) {
            verifyPackage(newPackage);
            cache.put(newPackage);

            installed[newPackage.name] =
                newPackage;

            lockFile.record(newPackage);

            std::cout
                << "  "
                << oldPackage.name
                << ": "
                << oldPackage.version.toString()
                << " -> "
                << newPackage.version.toString()
                << "\n";
        }

        history.push_back("upgrade-all");
    }

    bool verifyInstalled() const {
        std::cout
            << "\nVerifying installed artifacts\n";

        bool valid = true;

        for (const auto& [name, package] :
             installed) {
            if (package.checksum ==
                package.calculateChecksum()) {
                std::cout
                    << "  OK   "
                    << name
                    << "@"
                    << package.version.toString()
                    << "\n";
            } else {
                std::cout
                    << "  FAIL "
                    << name
                    << "@"
                    << package.version.toString()
                    << "\n";

                valid = false;
            }
        }

        return valid;
    }

    void listInstalled() const {
        std::cout
            << "\nInstalled packages\n";

        if (installed.empty()) {
            std::cout
                << "  none\n";
            return;
        }

        for (const auto& [name, package] :
             installed) {
            std::cout
                << "  "
                << name
                << "@"
                << package.version.toString()
                << " ("
                << package.sizeKB
                << " KB)\n";
        }
    }

    void printLockFile() const {
        std::cout
            << "\nLock file\n";

        lockFile.print();
    }

    void printHistory() const {
        std::cout
            << "\nTransaction history\n";

        for (std::size_t index = 0;
             index < history.size();
             ++index) {
            std::cout
                << "  "
                << std::setw(2)
                << std::setfill('0')
                << index + 1
                << ". "
                << history[index]
                << "\n";
        }

        std::cout << std::setfill(' ');
    }

    const std::map<std::string, Package>&
    installedPackages() const {
        return installed;
    }

    const ArtifactCache& getCache() const {
        return cache;
    }
};

// ============================================================================
// 11. DEPENDENCY GRAPH ANALYSIS
// ============================================================================

using DependencyGraph =
    std::map<std::string, std::set<std::string>>;

DependencyGraph buildGraph(
    const std::map<std::string, Package>& packages
) {
    DependencyGraph graph;

    for (const auto& [name, package] :
         packages) {
        for (const Dependency& dependency :
             package.dependencies) {
            graph[name].insert(
                dependency.name
            );
        }

        if (!graph.contains(name)) {
            graph[name] = {};
        }
    }

    return graph;
}

bool detectCycle(
    const DependencyGraph& graph
) {
    std::set<std::string> visiting;
    std::set<std::string> visited;

    std::function<bool(const std::string&)> visit =
        [&](const std::string& node) -> bool {
            if (visiting.contains(node)) {
                return true;
            }

            if (visited.contains(node)) {
                return false;
            }

            visiting.insert(node);

            auto iterator =
                graph.find(node);

            if (iterator != graph.end()) {
                for (const std::string& dependency :
                     iterator->second) {
                    if (visit(dependency)) {
                        return true;
                    }
                }
            }

            visiting.erase(node);
            visited.insert(node);

            return false;
        };

    for (const auto& [node, dependencies] :
         graph) {
        if (visit(node)) {
            return true;
        }
    }

    return false;
}

void printGraph(
    const DependencyGraph& graph
) {
    printSection("Resolved dependency graph");

    for (const auto& [name, dependencies] :
         graph) {
        std::cout
            << name
            << " -> ";

        if (dependencies.empty()) {
            std::cout << "none";
        } else {
            bool first = true;

            for (const std::string& dependency :
                 dependencies) {
                if (!first) {
                    std::cout << ", ";
                }

                std::cout << dependency;
                first = false;
            }
        }

        std::cout << "\n";
    }
}

// ============================================================================
// 12. SAMPLE REPOSITORY
// ============================================================================

Repository createRepository() {
    Repository repository(
        "company-central",
        true
    );

    repository.publish({
        "http-core",
        Version::parse("1.0.0"),
        {},
        180,
        "HTTP primitives",
        "any"
    });

    repository.publish({
        "http-core",
        Version::parse("1.1.0"),
        {},
        220,
        "HTTP primitives with pooling",
        "any"
    });

    repository.publish({
        "http-core",
        Version::parse("2.0.0"),
        {},
        300,
        "Redesigned HTTP API",
        "any"
    });

    repository.publish({
        "parser",
        Version::parse("1.0.0"),
        {
            {
                "http-core",
                VersionConstraint("^1.0.0")
            }
        },
        90,
        "Configuration parser",
        "any"
    });

    repository.publish({
        "parser",
        Version::parse("1.1.0"),
        {
            {
                "http-core",
                VersionConstraint("^1.0.0")
            }
        },
        110,
        "Improved configuration parser",
        "any"
    });

    repository.publish({
        "database-driver",
        Version::parse("3.0.0"),
        {
            {
                "http-core",
                VersionConstraint(">=1.1.0")
            }
        },
        750,
        "Database driver",
        "any"
    });

    repository.publish({
        "analytics-app",
        Version::parse("1.0.0"),
        {
            {
                "parser",
                VersionConstraint("^1.0.0")
            },
            {
                "database-driver",
                VersionConstraint("==3.0.0")
            }
        },
        1200,
        "Analytics application",
        "linux"
    });

    repository.publish({
        "analytics-app",
        Version::parse("1.1.0"),
        {
            {
                "parser",
                VersionConstraint("^1.1.0")
            },
            {
                "database-driver",
                VersionConstraint("==3.0.0")
            }
        },
        1300,
        "Updated analytics application",
        "linux"
    });

    return repository;
}

// ============================================================================
// 13. CONFLICT REPOSITORY
// ============================================================================

Repository createConflictRepository() {
    Repository repository(
        "conflict-repository",
        true
    );

    repository.publish({
        "core",
        Version::parse("1.5.0"),
        {},
        100,
        "Old core",
        "any"
    });

    repository.publish({
        "core",
        Version::parse("2.0.0"),
        {},
        150,
        "New core",
        "any"
    });

    repository.publish({
        "legacy-tool",
        Version::parse("1.0.0"),
        {
            {
                "core",
                VersionConstraint("<2.0.0")
            }
        },
        200,
        "Legacy integration",
        "any"
    });

    repository.publish({
        "modern-tool",
        Version::parse("1.0.0"),
        {
            {
                "core",
                VersionConstraint(">=2.0.0")
            }
        },
        250,
        "Modern integration",
        "any"
    });

    repository.publish({
        "conflicting-app",
        Version::parse("1.0.0"),
        {
            {
                "legacy-tool",
                VersionConstraint("==1.0.0")
            },
            {
                "modern-tool",
                VersionConstraint("==1.0.0")
            }
        },
        500,
        "Application with incompatible requirements",
        "any"
    });

    return repository;
}

// ============================================================================
// 14. SECURITY DEMONSTRATION
// ============================================================================

void explainSecurity() {
    printSection("Security controls");

    const std::vector<std::string> controls = {
        "Use trusted repositories.",
        "Verify hashes or digital signatures.",
        "Protect private repository credentials.",
        "Audit direct and transitive dependencies.",
        "Remove unused packages.",
        "Review package installation scripts.",
        "Use reproducible lock files in production.",
        "Keep package-management infrastructure updated.",
        "Use least privilege for installation operations.",
        "Treat package supply-chain compromise as a serious security event."
    };

    for (const auto& control : controls) {
        std::cout
            << "- "
            << control
            << "\n";
    }
}

// ============================================================================
// 15. COMPLEXITY DISCUSSION
// ============================================================================

void explainComplexity() {
    printSection("Algorithmic and operational considerations");

    std::cout
        << "Repository lookup:\n"
        << "  Indexed lookup can approach O(1) or O(log n), depending on storage.\n\n"

        << "Dependency traversal:\n"
        << "  A graph traversal is approximately O(V + E), where V is the number\n"
        << "  of packages and E is the number of dependency relationships.\n\n"

        << "Backtracking resolution:\n"
        << "  Worst-case search can grow exponentially when many independent\n"
        << "  version choices interact through constraints.\n\n"

        << "Caching:\n"
        << "  Avoids repeated artifact acquisition and can substantially reduce\n"
        << "  installation latency.\n\n"

        << "Integrity verification:\n"
        << "  Requires reading artifact data and therefore adds I/O and CPU work.\n";
}

// ============================================================================
// 16. CASE-STUDY TESTS
// ============================================================================

void runTests(
    const Repository& repository
) {
    printSection("Automated verification");

    if (!(Version::parse("1.2.3") <
          Version::parse("2.0.0"))) {
        throw std::runtime_error(
            "Version comparison test failed."
        );
    }

    VersionConstraint caret("^1.2.0");

    if (!caret.matches(
            Version::parse("1.9.9"))) {
        throw std::runtime_error(
            "Caret constraint test failed."
        );
    }

    if (caret.matches(
            Version::parse("2.0.0"))) {
        throw std::runtime_error(
            "Caret upper-bound test failed."
        );
    }

    VersionConstraint tilde("~1.2.0");

    if (!tilde.matches(
            Version::parse("1.2.9"))) {
        throw std::runtime_error(
            "Tilde constraint test failed."
        );
    }

    if (tilde.matches(
            Version::parse("1.3.0"))) {
        throw std::runtime_error(
            "Tilde upper-bound test failed."
        );
    }

    DependencyResolver resolver(
        std::vector<Repository>{repository}
    );

    auto resolved = resolver.resolve(
        "analytics-app",
        VersionConstraint("==1.0.0")
    );

    if (!resolved.contains("analytics-app") ||
        !resolved.contains("parser") ||
        !resolved.contains("database-driver") ||
        !resolved.contains("http-core")) {
        throw std::runtime_error(
            "Dependency resolution test failed."
        );
    }

    DependencyGraph graph =
        buildGraph(resolved);

    if (detectCycle(graph)) {
        throw std::runtime_error(
            "Unexpected dependency cycle."
        );
    }

    std::cout
        << "All tests passed.\n";
}

// ============================================================================
// 17. CONFLICT TEST
// ============================================================================

void runConflictTest() {
    printSection("Conflict detection");

    Repository repository =
        createConflictRepository();

    DependencyResolver resolver(
        std::vector<Repository>{repository}
    );

    try {
        resolver.resolve(
            "conflicting-app",
            VersionConstraint("==1.0.0")
        );

        throw std::runtime_error(
            "Expected conflict was not detected."
        );
    } catch (const ResolutionError& error) {
        std::cout
            << "Expected conflict:\n"
            << "  "
            << error.what()
            << "\n";
    }
}

// ============================================================================
// 18. MAIN CASE STUDY
// ============================================================================

int main() {
    try {
        printSection("PACKAGE MANAGEMENT C++ CASE STUDY");

        std::cout
            << "Scenario: dependency management for a modular analytics "
            << "platform.\n";

        Repository repository =
            createRepository();

        printSection("Repository inventory");
        repository.printContents();

        printSection("Initial dependency resolution");

        DependencyResolver resolver(
            std::vector<Repository>{repository}
        );

        auto resolved =
            resolver.resolve(
                "analytics-app",
                VersionConstraint("==1.0.0")
            );

        for (const auto& [name, package] :
             resolved) {
            std::cout
                << "  "
                << name
                << "@"
                << package.version.toString()
                << "\n";
        }

        DependencyGraph graph =
            buildGraph(resolved);

        printGraph(graph);

        std::cout
            << "\nDependency cycle detected: "
            << std::boolalpha
            << detectCycle(graph)
            << "\n";

        printSection("Package-manager transaction");

        PackageManager manager(
            std::vector<Repository>{repository}
        );

        manager.install(
            "analytics-app",
            VersionConstraint("==1.0.0")
        );

        manager.listInstalled();

        printSection("Integrity verification");

        bool integrity =
            manager.verifyInstalled();

        std::cout
            << "Integrity status: "
            << (integrity ? "valid" : "invalid")
            << "\n";

        manager.printLockFile();

        printSection("Upgrade operation");

        manager.upgradeAll();
        manager.listInstalled();
        manager.printLockFile();

        printSection("Cache inspection");

        auto cached =
            manager.getCache().get(
                "http-core",
                Version::parse("1.1.0")
            );

        std::cout
            << "http-core@1.1.0 cached: "
            << std::boolalpha
            << cached.has_value()
            << "\n";

        printSection("Removal protection");

        try {
            manager.remove("http-core");
        } catch (const std::exception& error) {
            std::cout
                << "Expected removal refusal:\n"
                << "  "
                << error.what()
                << "\n";
        }

        printSection("Failed transaction");

        /*
         * The package does not exist. The manager should fail without
         * damaging the already-installed state.
         */
        const auto before =
            manager.installedPackages().size();

        try {
            manager.install(
                "unknown-package",
                VersionConstraint("==1.0.0")
            );
        } catch (const std::exception& error) {
            std::cout
                << "Expected installation failure:\n"
                << "  "
                << error.what()
                << "\n";
        }

        const auto after =
            manager.installedPackages().size();

        std::cout
            << "Installed package count preserved: "
            << std::boolalpha
            << (before == after)
            << "\n";

        explainSecurity();
        explainComplexity();

        runConflictTest();
        runTests(repository);

        manager.printHistory();

        printSection("Architecture represented by the case study");

        std::cout
            << "Repository\n"
            << "    |\n"
            << "    v\n"
            << "Package metadata\n"
            << "    |\n"
            << "    v\n"
            << "Version constraints\n"
            << "    |\n"
            << "    v\n"
            << "Dependency resolver\n"
            << "    |\n"
            << "    v\n"
            << "Verified artifacts\n"
            << "    |\n"
            << "    v\n"
            << "Transaction\n"
            << "    |\n"
            << "    +----> Installed state\n"
            << "    |\n"
            << "    +----> Lock file\n"
            << "    |\n"
            << "    +----> Cache\n";

        printSection("Important production distinctions");

        std::cout
            << "A production package manager normally adds:\n"
            << "  - cryptographic signatures and trusted key infrastructure\n"
            << "  - platform and architecture constraints\n"
            << "  - richer version grammars\n"
            << "  - peer, optional, development, and build dependencies\n"
            << "  - repository priorities and mirrors\n"
            << "  - package metadata databases\n"
            << "  - lifecycle scripts and triggers\n"
            << "  - rollback mechanisms\n"
            << "  - concurrent downloads\n"
            << "  - vulnerability and policy checks\n"
            << "  - reproducible-build controls\n"
            << "  - sandboxing and privilege management\n";

        printSection("Case study complete");

        return 0;
    } catch (const std::exception& error) {
        std::cerr
            << "Fatal error: "
            << error.what()
            << "\n";

        return 1;
    }
}
