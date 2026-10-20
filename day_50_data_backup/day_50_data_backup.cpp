#include <algorithm>
#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace fs = std::filesystem;

enum class BackupType {
    Full,
    Incremental,
    Snapshot
};

struct FileRecord {
    std::string relativePath;
    std::uintmax_t size{};
    std::int64_t modifiedTicks{};
    std::string checksum;

    bool operator==(const FileRecord& other) const {
        return size == other.size &&
               modifiedTicks == other.modifiedTicks &&
               checksum == other.checksum;
    }
};

struct Backup {
    std::string id;
    BackupType type;
    std::string parentId;
    std::map<std::string, FileRecord> files;
    bool immutable{false};
};

struct ReviewResult {
    bool valid;
    std::vector<std::string> errors;
};

class BackupEngine {
private:
    fs::path repository;

    static std::string checksum(const fs::path& file) {
        // This deterministic checksum is deliberately lightweight for a
        // standard-library-only example. Production systems should use a
        // cryptographic hash such as SHA-256 through a vetted implementation.
        std::ifstream input(file, std::ios::binary);
        if (!input) {
            throw std::runtime_error("Unable to open " + file.string());
        }

        std::uint64_t hash = 1469598103934665603ULL;
        char byte;

        while (input.get(byte)) {
            hash ^= static_cast<unsigned char>(byte);
            hash *= 1099511628211ULL;
        }

        std::ostringstream output;
        output << std::hex << std::setw(16) << std::setfill('0') << hash;
        return output.str();
    }

    static std::int64_t modifiedTime(const fs::path& file) {
        return fs::last_write_time(file).time_since_epoch().count();
    }

    std::map<std::string, FileRecord> inventory(const fs::path& source) const {
        if (!fs::exists(source) || !fs::is_directory(source)) {
            throw std::runtime_error("Backup source is not a directory");
        }

        std::map<std::string, FileRecord> records;

        for (const auto& entry : fs::recursive_directory_iterator(source)) {
            if (!entry.is_regular_file()) {
                continue;
            }

            const auto relative = fs::relative(entry.path(), source).generic_string();

            records.emplace(
                relative,
                FileRecord{
                    relative,
                    entry.file_size(),
                    modifiedTime(entry.path()),
                    checksum(entry.path())
                }
            );
        }

        return records;
    }

    static bool safeRelativePath(const fs::path& relative) {
        if (relative.is_absolute()) {
            return false;
        }

        for (const auto& component : relative) {
            if (component == "..") {
                return false;
            }
        }

        return true;
    }

    void copyRecords(
        const fs::path& source,
        const fs::path& destination,
        const std::map<std::string, FileRecord>& records
    ) const {
        for (const auto& [relative, record] : records) {
            (void)record;

            fs::path relativePath(relative);
            if (!safeRelativePath(relativePath)) {
                throw std::runtime_error("Unsafe backup path: " + relative);
            }

            const fs::path sourceFile = source / relativePath;
            const fs::path targetFile = destination / relativePath;

            fs::create_directories(targetFile.parent_path());
            fs::copy_file(
                sourceFile,
                targetFile,
                fs::copy_options::overwrite_existing
            );
        }
    }

public:
    explicit BackupEngine(fs::path repositoryPath)
        : repository(std::move(repositoryPath)) {
        fs::create_directories(repository);
    }

    Backup createFull(const fs::path& source, const std::string& id) {
        const auto records = inventory(source);
        const fs::path target = repository / id;

        if (fs::exists(target)) {
            throw std::runtime_error("Backup already exists: " + id);
        }

        const fs::path temporary = repository / ("." + id + ".tmp");
        fs::remove_all(temporary);
        fs::create_directories(temporary);

        try {
            copyRecords(source, temporary, records);
            fs::rename(temporary, target);
        } catch (...) {
            fs::remove_all(temporary);
            throw;
        }

        return Backup{id, BackupType::Full, "", records, true};
    }

    Backup createIncremental(
        const fs::path& source,
        const Backup& parent,
        const std::string& id
    ) {
        const auto current = inventory(source);
        std::map<std::string, FileRecord> changed;

        for (const auto& [path, record] : current) {
            auto previous = parent.files.find(path);

            if (previous == parent.files.end() || !(previous->second == record)) {
                changed.emplace(path, record);
            }
        }

        const fs::path target = repository / id;
        const fs::path temporary = repository / ("." + id + ".tmp");

        fs::remove_all(temporary);
        fs::create_directories(temporary);

        try {
            copyRecords(source, temporary, changed);
            fs::rename(temporary, target);
        } catch (...) {
            fs::remove_all(temporary);
            throw;
        }

        return Backup{
            id,
            BackupType::Incremental,
            parent.id,
            changed,
            true
        };
    }

    Backup createSnapshot(
        const fs::path& source,
        const std::string& id
    ) {
        // A snapshot is modeled as an immutable point-in-time copy. Real
        // storage snapshots can be copy-on-write and need not copy every byte.
        return createFull(source, id);
    }

    ReviewResult verify(const Backup& backup) const {
        ReviewResult result{true, {}};
        const fs::path backupRoot = repository / backup.id;

        if (!fs::exists(backupRoot)) {
            return {false, {"Backup directory is missing"}};
        }

        for (const auto& [relative, expected] : backup.files) {
            if (!safeRelativePath(relative)) {
                result.valid = false;
                result.errors.push_back("Unsafe path: " + relative);
                continue;
            }

            const fs::path file = backupRoot / relative;

            if (!fs::exists(file) || !fs::is_regular_file(file)) {
                result.valid = false;
                result.errors.push_back("Missing file: " + relative);
                continue;
            }

            if (fs::file_size(file) != expected.size) {
                result.valid = false;
                result.errors.push_back("Size mismatch: " + relative);
                continue;
            }

            if (checksum(file) != expected.checksum) {
                result.valid = false;
                result.errors.push_back("Checksum mismatch: " + relative);
            }
        }

        return result;
    }

    bool mergeEligible(
        const Backup& full,
        const std::vector<Backup>& incrementals
    ) const {
        if (full.type != BackupType::Full) {
            return false;
        }

        Backup previous = full;

        for (const Backup& current : incrementals) {
            if (current.type != BackupType::Incremental ||
                current.parentId != previous.id) {
                return false;
            }

            if (!verify(current).valid) {
                return false;
            }

            previous = current;
        }

        return verify(full).valid;
    }
};

class RetentionPolicy {
private:
    std::chrono::hours retention;

public:
    explicit RetentionPolicy(int days)
        : retention(std::chrono::hours(24LL * days)) {
        if (days <= 0) {
            throw std::invalid_argument("Retention must be positive");
        }
    }

    bool expires(
        std::chrono::system_clock::time_point created,
        std::chrono::system_clock::time_point now
    ) const {
        return now - created > retention;
    }
};

int main() {
    try {
        const fs::path workspace =
            fs::temp_directory_path() / "backup_engine_case_study";

        fs::remove_all(workspace);
        fs::create_directories(workspace / "source" / "config");
        fs::create_directories(workspace / "source" / "logs");

        {
            std::ofstream(workspace / "source" / "config" / "app.conf")
                << "environment=production\n";
            std::ofstream(workspace / "source" / "logs" / "service.log")
                << "service started\n";
        }

        BackupEngine engine(workspace / "repository");

        Backup full = engine.createFull(
            workspace / "source",
            "full-20261001"
        );

        {
            std::ofstream(workspace / "source" / "logs" / "service.log",
                          std::ios::app)
                << "backup requested\n";
            std::ofstream(workspace / "source" / "config" / "feature.conf")
                << "incremental=true\n";
        }

        Backup incremental = engine.createIncremental(
            workspace / "source",
            full,
            "inc-20261002"
        );

        const ReviewResult fullCheck = engine.verify(full);
        const ReviewResult incrementalCheck = engine.verify(incremental);

        std::cout << "Full backup valid: "
                  << std::boolalpha << fullCheck.valid << '\n';

        std::cout << "Incremental backup valid: "
                  << incrementalCheck.valid << '\n';

        std::cout << "Restore chain eligible: "
                  << engine.mergeEligible(full, {incremental})
                  << '\n';

        RetentionPolicy policy(30);

        const auto now = std::chrono::system_clock::now();
        const auto created =
            now - std::chrono::hours(24LL * 31);

        std::cout << "Old backup expires: "
                  << policy.expires(created, now) << '\n';

        fs::remove_all(workspace);
    } catch (const std::exception& error) {
        std::cerr << "Backup engine failure: "
                  << error.what() << '\n';
        return 1;
    }

    return 0;
}
