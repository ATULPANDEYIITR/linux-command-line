import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.locks.ReentrantReadWriteLock;

/*
 * Docker Volumes: Enterprise Storage Governance
 *
 * Covers:
 * - Named, anonymous and bind mounts
 * - Container lifecycle
 * - Storage ownership
 * - Read-only policies
 * - Shared volume references
 * - Persistence and backup
 * - State transitions
 * - Merge-free storage operations
 *
 * Compile: javac DockerVolumes.java
 * Run: java DockerVolumes
 */

public class DockerVolumes {

    enum MountType {
        NAMED,
        ANONYMOUS,
        BIND
    }

    enum ContainerState {
        CREATED,
        RUNNING,
        STOPPED,
        REMOVED
    }

    enum StorageAction {
        READ,
        WRITE,
        DELETE
    }

    static class StorageException extends RuntimeException {
        StorageException(String message) {
            super(message);
        }
    }

    static class PolicyViolationException extends StorageException {
        PolicyViolationException(String message) {
            super(message);
        }
    }

    static class ResourceNotFoundException extends StorageException {
        ResourceNotFoundException(String message) {
            super(message);
        }
    }

    record StoragePolicy(
        boolean allowRead,
        boolean allowWrite,
        boolean allowDelete
    ) {
        void enforce(StorageAction action) {
            boolean permitted = switch (action) {
                case READ -> allowRead;
                case WRITE -> allowWrite;
                case DELETE -> allowDelete;
            };

            if (!permitted) {
                throw new PolicyViolationException(
                    "Storage action denied: " + action
                );
            }
        }

        static StoragePolicy readWrite() {
            return new StoragePolicy(true, true, true);
        }

        static StoragePolicy readOnly() {
            return new StoragePolicy(true, false, false);
        }
    }

    record Mount(
        String source,
        String target,
        MountType type,
        StoragePolicy policy
    ) {
        Mount {
            if (
                source == null ||
                source.isBlank() ||
                target == null ||
                !target.startsWith("/") ||
                List.of(target.split("/")).contains("..")
            ) {
                throw new IllegalArgumentException(
                    "Invalid mount configuration."
                );
            }
        }
    }

    static class Volume {
        private final String name;
        private final MountType type;
        private final Path hostPath;
        private final StoragePolicy policy;
        private final Map<String, String> labels;
        private final Set<String> references = new HashSet<>();

        Volume(
            String name,
            MountType type,
            Path hostPath,
            StoragePolicy policy,
            Map<String, String> labels
        ) {
            this.name = name;
            this.type = type;
            this.hostPath = hostPath;
            this.policy = policy;
            this.labels = Map.copyOf(labels);
        }

        String name() {
            return name;
        }

        MountType type() {
            return type;
        }

        Path hostPath() {
            return hostPath;
        }

        StoragePolicy policy() {
            return policy;
        }

        Set<String> references() {
            return Collections.unmodifiableSet(references);
        }

        Map<String, String> labels() {
            return labels;
        }
    }

    static class Container {
        private final String name;
        private final List<Mount> mounts;
        private final Map<String, String> writableLayer =
            new HashMap<>();

        private ContainerState state = ContainerState.CREATED;

        Container(String name, List<Mount> mounts) {
            this.name = name;
            this.mounts = List.copyOf(mounts);
        }

        String name() {
            return name;
        }

        ContainerState state() {
            return state;
        }

        List<Mount> mounts() {
            return mounts;
        }
    }

    interface StorageAudit {
        void record(String event, String resource);
    }

    static class ConsoleStorageAudit implements StorageAudit {
        @Override
        public void record(String event, String resource) {
            System.out.printf(
                "[AUDIT] %-24s %s%n",
                event,
                resource
            );
        }
    }

    static class StorageService {

        private final Path root;
        private final Path volumesDirectory;
        private final Path backupsDirectory;

        private final Map<String, Volume> volumes =
            new HashMap<>();

        private final Map<String, Container> containers =
            new HashMap<>();

        private final StorageAudit audit;

        private final ReentrantReadWriteLock lock =
            new ReentrantReadWriteLock();

        StorageService(Path root, StorageAudit audit)
            throws IOException {

            this.root = root.toAbsolutePath().normalize();
            this.volumesDirectory = this.root.resolve("volumes");
            this.backupsDirectory = this.root.resolve("backups");
            this.audit = audit;

            Files.createDirectories(volumesDirectory);
            Files.createDirectories(backupsDirectory);
        }

        private void validateName(String name) {
            if (
                name == null ||
                !name.matches("[a-zA-Z0-9_.-]{1,128}")
            ) {
                throw new IllegalArgumentException(
                    "Invalid resource name."
                );
            }
        }

        private void ensureUniqueVolume(String name) {
            if (volumes.containsKey(name)) {
                throw new PolicyViolationException(
                    "Storage resource already exists."
                );
            }
        }

        Volume createNamedVolume(
            String name,
            Map<String, String> labels
        ) throws IOException {

            lock.writeLock().lock();

            try {
                validateName(name);
                ensureUniqueVolume(name);

                Path directory = volumesDirectory.resolve(name)
                    .normalize();

                if (!directory.getParent().equals(volumesDirectory)) {
                    throw new PolicyViolationException(
                        "Invalid storage path."
                    );
                }

                Files.createDirectory(directory);

                Volume volume = new Volume(
                    name,
                    MountType.NAMED,
                    directory,
                    StoragePolicy.readWrite(),
                    labels
                );

                volumes.put(name, volume);

                audit.record("VOLUME_CREATED", name);

                return volume;

            } finally {
                lock.writeLock().unlock();
            }
        }

        Volume createAnonymousVolume() throws IOException {
            return createNamedVolume(
                "anonymous_" + UUID.randomUUID(),
                Map.of("kind", "anonymous")
            );
        }

        Volume createBindMount(
            String name,
            Path hostPath,
            StoragePolicy policy
        ) throws IOException {

            lock.writeLock().lock();

            try {
                validateName(name);
                ensureUniqueVolume(name);

                Path resolved = hostPath.toRealPath();

                if (!Files.isDirectory(resolved)) {
                    throw new IllegalArgumentException(
                        "Bind source must be a directory."
                    );
                }

                Volume volume = new Volume(
                    name,
                    MountType.BIND,
                    resolved,
                    policy,
                    Map.of("kind", "host-managed")
                );

                volumes.put(name, volume);

                audit.record("BIND_MOUNT_CREATED", name);

                return volume;

            } finally {
                lock.writeLock().unlock();
            }
        }

        Container createContainer(
            String name,
            List<Mount> mounts
        ) {

            lock.writeLock().lock();

            try {
                validateName(name);

                if (containers.containsKey(name)) {
                    throw new PolicyViolationException(
                        "Container already exists."
                    );
                }

                Set<String> destinations = new HashSet<>();

                // Validate every mount before changing reference counts.
                for (Mount mount : mounts) {
                    if (!destinations.add(mount.target())) {
                        throw new PolicyViolationException(
                            "Duplicate mount destination."
                        );
                    }

                    Volume volume = getVolume(mount.source());

                    if (volume.type() != mount.type()) {
                        throw new PolicyViolationException(
                            "Mount type mismatch."
                        );
                    }

                    if (
                        volume.policy().allowWrite() == false &&
                        mount.policy().allowWrite()
                    ) {
                        throw new PolicyViolationException(
                            "A read-only volume cannot receive a writable mount."
                        );
                    }
                }

                Container container = new Container(name, mounts);

                containers.put(name, container);

                for (Mount mount : mounts) {
                    getVolume(mount.source())
                        .references.add(name);
                }

                audit.record("CONTAINER_CREATED", name);

                return container;

            } finally {
                lock.writeLock().unlock();
            }
        }

        private Volume getVolume(String name) {
            Volume volume = volumes.get(name);

            if (volume == null) {
                throw new ResourceNotFoundException(
                    "Volume not found: " + name
                );
            }

            return volume;
        }

        private Container getContainer(String name) {
            Container container = containers.get(name);

            if (
                container == null ||
                container.state == ContainerState.REMOVED
            ) {
                throw new ResourceNotFoundException(
                    "Container not found: " + name
                );
            }

            return container;
        }

        void startContainer(String name) {
            lock.writeLock().lock();

            try {
                Container container = getContainer(name);

                if (container.state == ContainerState.RUNNING) {
                    return;
                }

                container.state = ContainerState.RUNNING;

                audit.record("CONTAINER_STARTED", name);

            } finally {
                lock.writeLock().unlock();
            }
        }

        void stopContainer(String name) {
            lock.writeLock().lock();

            try {
                Container container = getContainer(name);

                if (container.state != ContainerState.RUNNING) {
                    throw new PolicyViolationException(
                        "Container is not running."
                    );
                }

                container.state = ContainerState.STOPPED;

                audit.record("CONTAINER_STOPPED", name);

            } finally {
                lock.writeLock().unlock();
            }
        }

        private record ResolvedMount(
            Mount mount,
            Volume volume,
            Path destination
        ) {}

        private ResolvedMount resolve(
            Container container,
            String containerPath
        ) {

            if (
                containerPath == null ||
                !containerPath.startsWith("/") ||
                List.of(containerPath.split("/")).contains("..")
            ) {
                throw new IllegalArgumentException(
                    "Invalid container path."
                );
            }

            Mount selected = null;

            for (Mount mount : container.mounts) {
                if (
                    containerPath.equals(mount.target()) ||
                    containerPath.startsWith(mount.target() + "/")
                ) {
                    if (
                        selected == null ||
                        mount.target().length() > selected.target().length()
                    ) {
                        selected = mount;
                    }
                }
            }

            if (selected == null) {
                return null;
            }

            Volume volume = getVolume(selected.source());

            String relative = containerPath.substring(
                selected.target().length()
            );

            Path destination = volume.hostPath()
                .resolve(relative.startsWith("/")
                    ? relative.substring(1)
                    : relative)
                .normalize();

            if (!destination.startsWith(volume.hostPath())) {
                throw new PolicyViolationException(
                    "Storage path traversal detected."
                );
            }

            return new ResolvedMount(
                selected,
                volume,
                destination
            );
        }

        void writeFile(
            String containerName,
            String containerPath,
            String content
        ) throws IOException {

            lock.writeLock().lock();

            try {
                Container container = getContainer(containerName);

                if (container.state != ContainerState.RUNNING) {
                    throw new PolicyViolationException(
                        "Container must be running."
                    );
                }

                ResolvedMount resolved = resolve(
                    container,
                    containerPath
                );

                if (resolved == null) {
                    container.writableLayer.put(
                        containerPath,
                        content
                    );
                    return;
                }

                resolved.mount().policy().enforce(
                    StorageAction.WRITE
                );

                resolved.volume().policy().enforce(
                    StorageAction.WRITE
                );

                Files.createDirectories(
                    resolved.destination().getParent()
                );

                Files.writeString(
                    resolved.destination(),
                    content,
                    StandardCharsets.UTF_8
                );

                audit.record(
                    "FILE_WRITTEN",
                    containerName + ":" + containerPath
                );

            } finally {
                lock.writeLock().unlock();
            }
        }

        String readFile(
            String containerName,
            String containerPath
        ) throws IOException {

            lock.readLock().lock();

            try {
                Container container = getContainer(containerName);

                ResolvedMount resolved = resolve(
                    container,
                    containerPath
                );

                if (resolved == null) {
                    String content = container.writableLayer.get(
                        containerPath
                    );

                    if (content == null) {
                        throw new ResourceNotFoundException(
                            "Container file not found."
                        );
                    }

                    return content;
                }

                resolved.mount().policy().enforce(
                    StorageAction.READ
                );

                if (!Files.isRegularFile(resolved.destination())) {
                    throw new ResourceNotFoundException(
                        "Storage file does not exist."
                    );
                }

                return Files.readString(
                    resolved.destination(),
                    StandardCharsets.UTF_8
                );

            } finally {
                lock.readLock().unlock();
            }
        }

        void backupVolume(String name) throws IOException {
            lock.readLock().lock();

            try {
                Volume volume = getVolume(name);

                if (volume.type() == MountType.BIND) {
                    throw new PolicyViolationException(
                        "Bind mount backup is managed by host policy."
                    );
                }

                Path backup = backupsDirectory.resolve(
                    name + ".backup"
                );

                StringBuilder content = new StringBuilder();

                try (var paths = Files.walk(volume.hostPath())) {
                    for (Path file : paths.filter(Files::isRegularFile).toList()) {
                        if (Files.isSymbolicLink(file)) {
                            throw new PolicyViolationException(
                                "Symbolic links are not supported."
                            );
                        }

                        Path relative = volume.hostPath().relativize(file);

                        String data = Files.readString(
                            file,
                            StandardCharsets.UTF_8
                        );

                        content.append(relative)
                            .append('\n')
                            .append(data.length())
                            .append('\n')
                            .append(data)
                            .append('\n');
                    }
                }

                Files.writeString(
                    backup,
                    content.toString(),
                    StandardCharsets.UTF_8
                );

                audit.record("VOLUME_BACKED_UP", name);

            } finally {
                lock.readLock().unlock();
            }
        }

        void removeContainer(String name) {
            lock.writeLock().lock();

            try {
                Container container = getContainer(name);

                if (container.state == ContainerState.RUNNING) {
                    container.state = ContainerState.STOPPED;
                }

                for (Mount mount : container.mounts) {
                    getVolume(mount.source())
                        .references.remove(name);
                }

                container.writableLayer.clear();
                container.state = ContainerState.REMOVED;

                audit.record("CONTAINER_REMOVED", name);

            } finally {
                lock.writeLock().unlock();
            }
        }

        void removeVolume(String name, boolean force)
            throws IOException {

            lock.writeLock().lock();

            try {
                Volume volume = getVolume(name);

                if (!volume.references.isEmpty() && !force) {
                    throw new PolicyViolationException(
                        "Volume is still referenced by containers."
                    );
                }

                volume.policy().enforce(StorageAction.DELETE);

                if (volume.type() != MountType.BIND) {
                    try (var paths = Files.walk(volume.hostPath())) {
                        for (
                            Path file :
                            paths.sorted(
                                (a, b) -> b.compareTo(a)
                            ).toList()
                        ) {
                            Files.delete(file);
                        }
                    }
                }

                volumes.remove(name);

                audit.record("VOLUME_REMOVED", name);

            } finally {
                lock.writeLock().unlock();
            }
        }

        void printReport() throws IOException {
            lock.readLock().lock();

            try {
                long totalBytes = 0;

                System.out.println("\nStorage inventory");

                for (Volume volume : volumes.values()) {
                    long size = 0;

                    if (volume.type() != MountType.BIND) {
                        try (var paths = Files.walk(volume.hostPath())) {
                            size = paths
                                .filter(Files::isRegularFile)
                                .mapToLong(file -> {
                                    try {
                                        return Files.size(file);
                                    } catch (IOException error) {
                                        throw new StorageException(
                                            error.getMessage()
                                        );
                                    }
                                })
                                .sum();
                        }
                    }

                    totalBytes += size;

                    System.out.printf(
                        "%s | %s | %d bytes | %d references%n",
                        volume.name(),
                        volume.type(),
                        size,
                        volume.references.size()
                    );
                }

                System.out.println("Total bytes: " + totalBytes);

            } finally {
                lock.readLock().unlock();
            }
        }
    }

    public static void main(String[] args) {
        Path root = null;

        try {
            root = Files.createTempDirectory(
                "docker-enterprise-storage-"
            );

            StorageService service = new StorageService(
                root,
                new ConsoleStorageAudit()
            );

            // Database storage.
            service.createNamedVolume(
                "postgres_data",
                Map.of(
                    "environment", "development",
                    "owner", "database-team"
                )
            );

            service.createContainer(
                "postgres",
                List.of(
                    new Mount(
                        "postgres_data",
                        "/var/lib/postgresql/data",
                        MountType.NAMED,
                        StoragePolicy.readWrite()
                    )
                )
            );

            service.startContainer("postgres");

            service.writeFile(
                "postgres",
                "/var/lib/postgresql/data/database.txt",
                "Persistent application records"
            );

            service.writeFile(
                "postgres",
                "/tmp/session.txt",
                "Temporary container layer"
            );

            if (!service.readFile(
                "postgres",
                "/var/lib/postgresql/data/database.txt"
            ).equals("Persistent application records")) {
                throw new AssertionError("Volume persistence failed.");
            }

            // Protect storage from deletion while in use.
            try {
                service.removeVolume("postgres_data", false);

                throw new AssertionError(
                    "Expected deletion protection."
                );

            } catch (PolicyViolationException expected) {
                System.out.println(
                    "Active volume deletion rejected."
                );
            }

            service.backupVolume("postgres_data");

            service.removeContainer("postgres");

            // Reattach persistent storage to a new container.
            service.createContainer(
                "postgres_recovery",
                List.of(
                    new Mount(
                        "postgres_data",
                        "/var/lib/postgresql/data",
                        MountType.NAMED,
                        StoragePolicy.readWrite()
                    )
                )
            );

            service.startContainer("postgres_recovery");

            if (!service.readFile(
                "postgres_recovery",
                "/var/lib/postgresql/data/database.txt"
            ).equals("Persistent application records")) {
                throw new AssertionError(
                    "Data was not preserved."
                );
            }

            // Host-managed configuration.
            Path hostConfig = Files.createDirectory(
                root.resolve("host-config")
            );

            Files.writeString(
                hostConfig.resolve("settings.txt"),
                "Host-controlled configuration"
            );

            service.createBindMount(
                "application_config",
                hostConfig,
                StoragePolicy.readOnly()
            );

            service.createContainer(
                "application",
                List.of(
                    new Mount(
                        "application_config",
                        "/etc/application",
                        MountType.BIND,
                        StoragePolicy.readOnly()
                    )
                )
            );

            service.startContainer("application");

            if (!service.readFile(
                "application",
                "/etc/application/settings.txt"
            ).equals("Host-controlled configuration")) {
                throw new AssertionError("Bind mount failed.");
            }

            try {
                service.writeFile(
                    "application",
                    "/etc/application/settings.txt",
                    "Unauthorized modification"
                );

                throw new AssertionError(
                    "Read-only policy was not enforced."
                );

            } catch (PolicyViolationException expected) {
                System.out.println(
                    "Read-only policy correctly enforced."
                );
            }

            service.removeContainer("application");
            service.removeContainer("postgres_recovery");

            service.removeVolume("postgres_data", false);

            service.printReport();

            System.out.println(
                "\nAll enterprise storage tests passed."
            );

        } catch (Exception error) {
            System.err.println(
                "Storage failure: " + error.getMessage()
            );

            System.exitCode = 1;

        } finally {
            if (root != null) {
                try (var paths = Files.walk(root)) {
                    for (
                        Path file :
                        paths.sorted(
                            (a, b) -> b.compareTo(a)
                        ).toList()
                    ) {
                        Files.deleteIfExists(file);
                    }
                } catch (IOException error) {
                    System.err.println(
                        "Cleanup failure: " + error.getMessage()
                    );
                }
            }
        }
    }
}
