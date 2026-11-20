#include <algorithm>
#include <cstdint>
#include <filesystem>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

namespace fs = std::filesystem;

enum class MountType {
    Named,
    Anonymous,
    Bind
};

enum class ContainerState {
    Created,
    Running,
    Stopped,
    Removed
};

std::string toString(MountType type) {
    switch (type) {
        case MountType::Named: return "named";
        case MountType::Anonymous: return "anonymous";
        case MountType::Bind: return "bind";
    }
    throw std::logic_error("Unknown mount type");
}

std::string toString(ContainerState state) {
    switch (state) {
        case ContainerState::Created: return "created";
        case ContainerState::Running: return "running";
        case ContainerState::Stopped: return "stopped";
        case ContainerState::Removed: return "removed";
    }
    throw std::logic_error("Unknown container state");
}

struct Volume {
    std::string name;
    MountType type;
    fs::path hostPath;
    bool readOnly = false;
    std::set<std::string> references;
    std::map<std::string, std::string> labels;
};

struct Mount {
    std::string source;
    fs::path target;
    MountType type;
    bool readOnly = false;
};

struct Container {
    std::string name;
    ContainerState state = ContainerState::Created;
    std::vector<Mount> mounts;
    std::map<std::string, std::string> writableLayer;
};

struct StorageReport {
    std::size_t volumeCount = 0;
    std::uintmax_t totalBytes = 0;
    std::size_t activeReferences = 0;
};

class StorageEngine {
private:
    fs::path root;
    fs::path volumeDirectory;
    fs::path backupDirectory;

    std::map<std::string, Volume> volumes;
    std::map<std::string, Container> containers;

    static void validateName(const std::string& name) {
        if (name.empty() || name.size() > 128) {
            throw std::invalid_argument("Invalid storage name");
        }

        for (unsigned char c : name) {
            if (
                !std::isalnum(c) &&
                c != '_' &&
                c != '-' &&
                c != '.'
            ) {
                throw std::invalid_argument("Invalid storage name");
            }
        }
    }

    static void validateTarget(const fs::path& target) {
        if (!target.is_absolute()) {
            throw std::invalid_argument(
                "Container mount target must be absolute"
            );
        }

        for (const auto& part : target) {
            if (part == "..") {
                throw std::invalid_argument(
                    "Path traversal is not allowed"
                );
            }
        }
    }

    static bool inside(
        const fs::path& parent,
        const fs::path& child
    ) {
        auto p = parent.begin();
        auto c = child.begin();

        for (; p != parent.end(); ++p, ++c) {
            if (c == child.end() || *p != *c) {
                return false;
            }
        }

        return true;
    }

    Volume& getVolume(const std::string& name) {
        auto it = volumes.find(name);

        if (it == volumes.end()) {
            throw std::runtime_error("Volume not found: " + name);
        }

        return it->second;
    }

    Container& getContainer(const std::string& name) {
        auto it = containers.find(name);

        if (
            it == containers.end() ||
            it->second.state == ContainerState::Removed
        ) {
            throw std::runtime_error("Container not found: " + name);
        }

        return it->second;
    }

    std::optional<std::pair<Mount*, fs::path>>
    resolveMount(Container& container, const fs::path& target) {
        validateTarget(target);

        Mount* selected = nullptr;
        std::size_t longest = 0;

        for (auto& mount : container.mounts) {
            if (
                inside(mount.target, target) &&
                mount.target.native().size() >= longest
            ) {
                selected = &mount;
                longest = mount.target.native().size();
            }
        }

        if (!selected) {
            return std::nullopt;
        }

        fs::path relative = target.lexically_relative(
            selected->target
        );

        Volume& volume = getVolume(selected->source);

        fs::path destination = (
            volume.hostPath / relative
        ).lexically_normal();

        if (!inside(volume.hostPath, destination)) {
            throw std::runtime_error(
                "Resolved storage path escaped volume"
            );
        }

        return std::make_pair(selected, destination);
    }

public:
    explicit StorageEngine(fs::path storageRoot)
        : root(fs::absolute(std::move(storageRoot)).lexically_normal()),
          volumeDirectory(root / "volumes"),
          backupDirectory(root / "backups") {

        fs::create_directories(volumeDirectory);
        fs::create_directories(backupDirectory);
    }

    void createNamedVolume(
        const std::string& name,
        std::map<std::string, std::string> labels = {}
    ) {
        validateName(name);

        if (volumes.count(name)) {
            throw std::runtime_error("Volume already exists");
        }

        fs::path directory = volumeDirectory / name;

        fs::create_directory(directory);

        volumes.emplace(
            name,
            Volume{
                name,
                MountType::Named,
                directory,
                false,
                {},
                std::move(labels)
            }
        );
    }

    void createAnonymousVolume(const std::string& name) {
        validateName(name);

        if (volumes.count(name)) {
            throw std::runtime_error("Volume already exists");
        }

        fs::path directory = volumeDirectory / name;

        fs::create_directory(directory);

        volumes.emplace(
            name,
            Volume{
                name,
                MountType::Anonymous,
                directory
            }
        );
    }

    void createBindMount(
        const std::string& name,
        const fs::path& source,
        bool readOnly = false
    ) {
        validateName(name);

        if (volumes.count(name)) {
            throw std::runtime_error("Mount name already exists");
        }

        if (!fs::is_directory(source)) {
            throw std::runtime_error(
                "Bind source must be an existing directory"
            );
        }

        fs::path resolved = fs::canonical(source);

        volumes.emplace(
            name,
            Volume{
                name,
                MountType::Bind,
                resolved,
                readOnly
            }
        );
    }

    void createContainer(
        const std::string& name,
        const std::vector<Mount>& mounts
    ) {
        validateName(name);

        if (containers.count(name)) {
            throw std::runtime_error("Container already exists");
        }

        std::set<std::string> destinations;

        for (const auto& mount : mounts) {
            validateTarget(mount.target);

            if (!destinations.insert(
                mount.target.generic_string()
            ).second) {
                throw std::runtime_error(
                    "Duplicate mount destination"
                );
            }

            Volume& volume = getVolume(mount.source);

            if (volume.type != mount.type) {
                throw std::runtime_error(
                    "Mount type does not match storage type"
                );
            }

            if (volume.readOnly && !mount.readOnly) {
                throw std::runtime_error(
                    "Read-only storage cannot be mounted writable"
                );
            }
        }

        Container container;
        container.name = name;
        container.mounts = mounts;

        containers.emplace(name, std::move(container));

        for (const auto& mount : mounts) {
            getVolume(mount.source).references.insert(name);
        }
    }

    void startContainer(const std::string& name) {
        Container& container = getContainer(name);

        if (container.state == ContainerState::Running) {
            return;
        }

        container.state = ContainerState::Running;
    }

    void stopContainer(const std::string& name) {
        Container& container = getContainer(name);

        if (container.state != ContainerState::Running) {
            throw std::runtime_error("Container is not running");
        }

        container.state = ContainerState::Stopped;
    }

    void writeFile(
        const std::string& containerName,
        const fs::path& containerPath,
        const std::string& content
    ) {
        Container& container = getContainer(containerName);

        if (container.state != ContainerState::Running) {
            throw std::runtime_error("Container must be running");
        }

        auto resolved = resolveMount(container, containerPath);

        if (!resolved) {
            container.writableLayer[
                containerPath.generic_string()
            ] = content;

            return;
        }

        Mount* mount = resolved->first;
        fs::path destination = resolved->second;

        if (mount->readOnly) {
            throw std::runtime_error("Mount is read-only");
        }

        fs::create_directories(destination.parent_path());

        std::ofstream output(
            destination,
            std::ios::binary | std::ios::trunc
        );

        if (!output) {
            throw std::runtime_error("Unable to open storage file");
        }

        output << content;

        if (!output.good()) {
            throw std::runtime_error("Storage write failed");
        }
    }

    std::string readFile(
        const std::string& containerName,
        const fs::path& containerPath
    ) {
        Container& container = getContainer(containerName);

        auto resolved = resolveMount(container, containerPath);

        if (!resolved) {
            auto it = container.writableLayer.find(
                containerPath.generic_string()
            );

            if (it == container.writableLayer.end()) {
                throw std::runtime_error("File not found");
            }

            return it->second;
        }

        std::ifstream input(resolved->second, std::ios::binary);

        if (!input) {
            throw std::runtime_error("Unable to read storage file");
        }

        return std::string(
            std::istreambuf_iterator<char>(input),
            std::istreambuf_iterator<char>()
        );
    }

    void removeContainer(const std::string& name) {
        Container& container = getContainer(name);

        if (container.state == ContainerState::Running) {
            container.state = ContainerState::Stopped;
        }

        for (const auto& mount : container.mounts) {
            getVolume(mount.source).references.erase(name);
        }

        // The writable layer disappears; volumes remain intact.
        container.writableLayer.clear();
        container.state = ContainerState::Removed;
    }

    void removeVolume(
        const std::string& name,
        bool force = false
    ) {
        Volume& volume = getVolume(name);

        if (!volume.references.empty() && !force) {
            throw std::runtime_error(
                "Cannot remove a volume used by containers"
            );
        }

        if (volume.type != MountType::Bind) {
            fs::remove_all(volume.hostPath);
        }

        volumes.erase(name);
    }

    void backupVolume(const std::string& name) {
        Volume& volume = getVolume(name);

        if (volume.type == MountType::Bind) {
            throw std::runtime_error(
                "Bind mounts require a host-specific backup procedure"
            );
        }

        fs::path destination = backupDirectory / (name + ".backup");

        std::ofstream output(destination, std::ios::binary);

        if (!output) {
            throw std::runtime_error("Unable to create backup");
        }

        for (
            const auto& entry :
            fs::recursive_directory_iterator(volume.hostPath)
        ) {
            if (entry.is_symlink()) {
                throw std::runtime_error(
                    "Symbolic links are not supported"
                );
            }

            if (!entry.is_regular_file()) {
                continue;
            }

            fs::path relative = fs::relative(
                entry.path(),
                volume.hostPath
            );

            std::ifstream input(entry.path(), std::ios::binary);

            if (!input) {
                throw std::runtime_error("Backup read failed");
            }

            std::string content(
                std::istreambuf_iterator<char>(input),
                std::istreambuf_iterator<char>()
            );

            output << relative.generic_string() << '\n';
            output << content.size() << '\n';
            output.write(
                content.data(),
                static_cast<std::streamsize>(content.size())
            );
            output << '\n';
        }

        if (!output.good()) {
            throw std::runtime_error("Backup write failed");
        }
    }

    StorageReport report() const {
        StorageReport result;

        result.volumeCount = volumes.size();

        for (const auto& [name, volume] : volumes) {
            result.activeReferences += volume.references.size();

            if (volume.type == MountType::Bind) {
                continue;
            }

            for (
                const auto& entry :
                fs::recursive_directory_iterator(volume.hostPath)
            ) {
                if (
                    entry.is_regular_file() &&
                    !entry.is_symlink()
                ) {
                    result.totalBytes += entry.file_size();
                }
            }
        }

        return result;
    }

    void printVolumes() const {
        for (const auto& [name, volume] : volumes) {
            std::cout
                << name
                << " | " << toString(volume.type)
                << " | references=" << volume.references.size()
                << " | path=" << volume.hostPath
                << '\n';
        }
    }
};

int main() {
    try {
        fs::path root = fs::temp_directory_path()
            / "docker-volume-governance-demo";

        fs::remove_all(root);

        StorageEngine engine(root);

        // Create independent persistent storage.
        engine.createNamedVolume(
            "postgres_data",
            {
                {"environment", "development"},
                {"service", "postgres"}
            }
        );

        engine.createContainer(
            "postgres",
            {
                {
                    "postgres_data",
                    "/var/lib/postgresql/data",
                    MountType::Named,
                    false
                }
            }
        );

        engine.startContainer("postgres");

        engine.writeFile(
            "postgres",
            "/var/lib/postgresql/data/database.txt",
            "Persistent database records"
        );

        engine.writeFile(
            "postgres",
            "/tmp/cache.txt",
            "Temporary writable layer"
        );

        if (
            engine.readFile(
                "postgres",
                "/var/lib/postgresql/data/database.txt"
            ) != "Persistent database records"
        ) {
            throw std::runtime_error("Persistence test failed");
        }

        // A volume referenced by a container cannot be removed.
        try {
            engine.removeVolume("postgres_data");

            throw std::runtime_error(
                "Expected in-use volume protection"
            );
        } catch (const std::runtime_error& error) {
            std::cout << "In-use deletion rejected: "
                      << error.what() << '\n';
        }

        engine.backupVolume("postgres_data");

        engine.removeContainer("postgres");

        // Container writable-layer data is gone.
        // Named volume data remains available.
        engine.createContainer(
            "postgres_recovery",
            {
                {
                    "postgres_data",
                    "/var/lib/postgresql/data",
                    MountType::Named,
                    false
                }
            }
        );

        engine.startContainer("postgres_recovery");

        if (
            engine.readFile(
                "postgres_recovery",
                "/var/lib/postgresql/data/database.txt"
            ) != "Persistent database records"
        ) {
            throw std::runtime_error(
                "Persistent storage recovery failed"
            );
        }

        // Host-controlled bind mount.
        fs::path hostDirectory = root / "host-config";
        fs::create_directories(hostDirectory);

        {
            std::ofstream config(hostDirectory / "config.txt");
            config << "Host-managed configuration";
        }

        engine.createBindMount(
            "application_config",
            hostDirectory,
            true
        );

        engine.createContainer(
            "application",
            {
                {
                    "application_config",
                    "/etc/application",
                    MountType::Bind,
                    true
                }
            }
        );

        engine.startContainer("application");

        if (
            engine.readFile(
                "application",
                "/etc/application/config.txt"
            ) != "Host-managed configuration"
        ) {
            throw std::runtime_error("Bind mount test failed");
        }

        try {
            engine.writeFile(
                "application",
                "/etc/application/config.txt",
                "Unauthorized modification"
            );

            throw std::runtime_error(
                "Expected read-only write protection"
            );
        } catch (const std::runtime_error& error) {
            std::cout << "Read-only protection: "
                      << error.what() << '\n';
        }

        engine.removeContainer("application");
        engine.removeContainer("postgres_recovery");

        engine.removeVolume("postgres_data");

        StorageReport report = engine.report();

        std::cout << "\nStorage report\n";
        std::cout << "Volumes: " << report.volumeCount << '\n';
        std::cout << "Total bytes: " << report.totalBytes << '\n';
        std::cout << "Active references: "
                  << report.activeReferences << '\n';

        engine.printVolumes();

        std::cout << "\nAll storage tests passed.\n";

        fs::remove_all(root);

        return 0;

    } catch (const std::exception& error) {
        std::cerr << "Storage error: "
                  << error.what() << '\n';

        return 1;
    }
}
