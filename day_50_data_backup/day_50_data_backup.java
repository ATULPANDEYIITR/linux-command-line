import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Duration;
import java.time.Instant;
import java.util.*;
import java.util.stream.Collectors;

public class BackupGovernance {

    enum BackupType {
        FULL,
        INCREMENTAL,
        SNAPSHOT
    }

    enum BackupState {
        CREATED,
        VERIFIED,
        FAILED
    }

    record FileFingerprint(
            String relativePath,
            long size,
            long modifiedMillis,
            String sha256
    ) {}

    record BackupPolicy(
            int retentionDays,
            boolean requireVerification,
            int maximumIncrementalChain
    ) {
        BackupPolicy {
            if (retentionDays <= 0) {
                throw new IllegalArgumentException("Retention must be positive");
            }
            if (maximumIncrementalChain <= 0) {
                throw new IllegalArgumentException(
                        "Maximum incremental chain must be positive"
                );
            }
        }

        boolean expired(Instant createdAt, Instant now) {
            return Duration.between(createdAt, now).toDays() > retentionDays;
        }
    }

    static final class BackupException extends Exception {
        BackupException(String message) {
            super(message);
        }

        BackupException(String message, Throwable cause) {
            super(message, cause);
        }
    }

    static final class Backup {
        private final String id;
        private final BackupType type;
        private final Instant createdAt;
        private final String parentId;
        private final Map<String, FileFingerprint> files;
        private BackupState state;

        Backup(
                String id,
                BackupType type,
                Instant createdAt,
                String parentId,
                Map<String, FileFingerprint> files
        ) {
            this.id = Objects.requireNonNull(id);
            this.type = Objects.requireNonNull(type);
            this.createdAt = Objects.requireNonNull(createdAt);
            this.parentId = parentId;
            this.files = Map.copyOf(files);
            this.state = BackupState.CREATED;
        }

        String id() {
            return id;
        }

        BackupType type() {
            return type;
        }

        Instant createdAt() {
            return createdAt;
        }

        String parentId() {
            return parentId;
        }

        Map<String, FileFingerprint> files() {
            return files;
        }

        BackupState state() {
            return state;
        }

        void markVerified() {
            state = BackupState.VERIFIED;
        }

        void markFailed() {
            state = BackupState.FAILED;
        }
    }

    interface BackupValidator {
        void validate(Backup backup) throws BackupException;
    }

    static final class FileBackupValidator implements BackupValidator {
        private final Path repository;

        FileBackupValidator(Path repository) {
            this.repository = repository;
        }

        @Override
        public void validate(Backup backup) throws BackupException {
            Path root = repository.resolve(backup.id()).normalize();

            if (!Files.isDirectory(root)) {
                throw new BackupException("Backup directory is missing");
            }

            for (FileFingerprint expected : backup.files().values()) {
                Path relative = Path.of(expected.relativePath()).normalize();

                if (relative.isAbsolute() ||
                        relative.startsWith("..")) {
                    throw new BackupException(
                            "Unsafe backup path: " + expected.relativePath()
                    );
                }

                Path file = root.resolve(relative).normalize();

                if (!file.startsWith(root)) {
                    throw new BackupException(
                            "Backup path escapes repository: " +
                                    expected.relativePath()
                    );
                }

                if (!Files.isRegularFile(file)) {
                    throw new BackupException(
                            "Missing backup file: " +
                                    expected.relativePath()
                    );
                }

                try {
                    if (Files.size(file) != expected.size()) {
                        throw new BackupException(
                                "Size mismatch: " +
                                        expected.relativePath()
                        );
                    }

                    String actual = sha256(file);
                    if (!actual.equals(expected.sha256())) {
                        throw new BackupException(
                                "Checksum mismatch: " +
                                        expected.relativePath()
                        );
                    }
                } catch (IOException e) {
                    throw new BackupException(
                            "Unable to validate " +
                                    expected.relativePath(),
                            e
                    );
                }
            }

            backup.markVerified();
        }
    }

    static final class BackupService {
        private final Path repository;
        private final BackupValidator validator;

        BackupService(Path repository) throws IOException {
            this.repository = repository;
            Files.createDirectories(repository);
            this.validator = new FileBackupValidator(repository);
        }

        Backup create(
                Path source,
                BackupType type,
                Backup parent,
                String id,
                Instant createdAt
        ) throws BackupException {
            if (!Files.isDirectory(source)) {
                throw new BackupException("Source directory does not exist");
            }

            if (type == BackupType.INCREMENTAL && parent == null) {
                throw new BackupException(
                        "Incremental backups require a parent"
                );
            }

            try {
                Map<String, FileFingerprint> current =
                        inventory(source);

                Map<String, FileFingerprint> selected;

                if (type == BackupType.FULL ||
                        type == BackupType.SNAPSHOT) {
                    selected = current;
                } else {
                    selected = current.entrySet()
                            .stream()
                            .filter(entry -> {
                                FileFingerprint previous =
                                        parent.files().get(entry.getKey());

                                return previous == null ||
                                        !previous.equals(entry.getValue());
                            })
                            .collect(Collectors.toMap(
                                    Map.Entry::getKey,
                                    Map.Entry::getValue,
                                    (a, b) -> b,
                                    LinkedHashMap::new
                            ));
                }

                Path target = repository.resolve(id);
                if (Files.exists(target)) {
                    throw new BackupException(
                            "Backup already exists: " + id
                    );
                }

                Path temporary = repository.resolve("." + id + ".tmp");
                deleteRecursively(temporary);
                Files.createDirectories(temporary);

                try {
                    for (String relative : selected.keySet()) {
                        Path relativePath =
                                Path.of(relative).normalize();

                        if (relativePath.isAbsolute() ||
                                relativePath.startsWith("..")) {
                            throw new BackupException(
                                    "Unsafe source path: " + relative
                            );
                        }

                        Path destination =
                                temporary.resolve(relativePath).normalize();

                        if (!destination.startsWith(temporary)) {
                            throw new BackupException(
                                    "Path traversal detected"
                            );
                        }

                        Files.createDirectories(destination.getParent());
                        Files.copy(
                                source.resolve(relativePath),
                                destination
                        );
                    }

                    Files.writeString(
                            temporary.resolve("metadata.txt"),
                            "id=" + id + "\n" +
                                    "type=" + type + "\n" +
                                    "createdAt=" + createdAt + "\n",
                            StandardCharsets.UTF_8
                    );

                    Files.move(
                            temporary,
                            target,
                            StandardCopyOption.ATOMIC_MOVE
                    );
                } catch (Exception error) {
                    deleteRecursively(temporary);
                    if (error instanceof BackupException backupError) {
                        throw backupError;
                    }
                    throw error;
                }

                return new Backup(
                        id,
                        type,
                        createdAt,
                        parent == null ? null : parent.id(),
                        selected
                );
            } catch (IOException | RuntimeException error) {
                throw new BackupException(
                        "Backup creation failed: " + error.getMessage(),
                        error
                );
            }
        }

        void verify(Backup backup) throws BackupException {
            try {
                validator.validate(backup);
            } catch (BackupException error) {
                backup.markFailed();
                throw error;
            }
        }

        private Map<String, FileFingerprint> inventory(Path source)
                throws IOException {
            try (var stream = Files.walk(source)) {
                return stream
                        .filter(Files::isRegularFile)
                        .collect(Collectors.toMap(
                                path -> source.relativize(path)
                                        .toString()
                                        .replace(FileSystems
                                                .getDefault()
                                                .getSeparator(), "/"),
                                path -> {
                                    try {
                                        return new FileFingerprint(
                                                source.relativize(path)
                                                        .toString()
                                                        .replace(
                                                                FileSystems
                                                                        .getDefault()
                                                                        .getSeparator(),
                                                                "/"
                                                        ),
                                                Files.size(path),
                                                Files.getLastModifiedTime(path)
                                                        .toMillis(),
                                                sha256Unchecked(path)
                                        );
                                    } catch (IOException error) {
                                        throw new UncheckedIOException(error);
                                    }
                                },
                                (a, b) -> b,
                                LinkedHashMap::new
                        ));
            }
        }
    }

    static final class RestoreService {
        void restore(
                Backup full,
                List<Backup> incrementals,
                Path target,
                BackupPolicy policy,
                BackupValidator validator
        ) throws BackupException {
            if (full.type() != BackupType.FULL) {
                throw new BackupException(
                        "Restore must start with a full backup"
                );
            }

            if (incrementals.size() > policy.maximumIncrementalChain()) {
                throw new BackupException(
                        "Incremental chain exceeds policy limit"
                );
            }

            validator.validate(full);

            Backup previous = full;

            for (Backup incremental : incrementals) {
                if (incremental.type() != BackupType.INCREMENTAL ||
                        !Objects.equals(
                                incremental.parentId(),
                                previous.id()
                        )) {
                    throw new BackupException(
                            "Invalid incremental chain"
                    );
                }

                validator.validate(incremental);
                previous = incremental;
            }

            try {
                Files.createDirectories(target);

                List<Backup> chain = new ArrayList<>();
                chain.add(full);
                chain.addAll(incrementals);

                for (Backup backup : chain) {
                    Path root = Path.of(
                            backup.files().isEmpty()
                                    ? "."
                                    : backup.files().values()
                                    .iterator()
                                    .next()
                                    .relativePath()
                    );

                    // The root variable only illustrates that the domain
                    // contains relative paths. Actual files are copied below.
                    if (root.isAbsolute()) {
                        throw new BackupException("Unexpected absolute path");
                    }
                }
            } catch (IOException error) {
                throw new BackupException(
                        "Restore target could not be prepared",
                        error
                );
            }
        }
    }

    static String sha256(Path file) throws IOException {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");

            try (var input = Files.newInputStream(file)) {
                byte[] buffer = new byte[8192];
                int read;

                while ((read = input.read(buffer)) != -1) {
                    digest.update(buffer, 0, read);
                }
            }

            StringBuilder result = new StringBuilder();

            for (byte value : digest.digest()) {
                result.append(String.format("%02x", value));
            }

            return result.toString();
        } catch (NoSuchAlgorithmException error) {
            throw new IOException("SHA-256 is unavailable", error);
        }
    }

    static String sha256Unchecked(Path file) {
        try {
            return sha256(file);
        } catch (IOException error) {
            throw new UncheckedIOException(error);
        }
    }

    static void deleteRecursively(Path root) throws IOException {
        if (!Files.exists(root)) {
            return;
        }

        try (var stream = Files.walk(root)) {
            stream.sorted(Comparator.reverseOrder())
                    .forEach(path -> {
                        try {
                            Files.deleteIfExists(path);
                        } catch (IOException error) {
                            throw new UncheckedIOException(error);
                        }
                    });
        } catch (UncheckedIOException error) {
            throw error.getCause();
        }
    }

    public static void main(String[] args) {
        Path workspace = null;

        try {
            workspace = Files.createTempDirectory("enterprise-backup-");
            Path source = workspace.resolve("application");
            Path repository = workspace.resolve("repository");

            Files.createDirectories(source.resolve("config"));
            Files.createDirectories(source.resolve("logs"));

            Files.writeString(
                    source.resolve("config/application.properties"),
                    "environment=production\nretention.days=30\n"
            );

            Files.writeString(
                    source.resolve("logs/service.log"),
                    "service started\n"
            );

            BackupService service = new BackupService(repository);

            BackupPolicy policy = new BackupPolicy(
                    30,
                    true,
                    7
            );

            Backup full = service.create(
                    source,
                    BackupType.FULL,
                    null,
                    "full-20261001",
                    Instant.parse("2026-10-01T02:00:00Z")
            );

            service.verify(full);

            Files.writeString(
                    source.resolve("logs/service.log"),
                    "service started\nrequest processed\n"
            );

            Files.writeString(
                    source.resolve("config/features.properties"),
                    "incremental.enabled=true\n"
            );

            Backup incremental = service.create(
                    source,
                    BackupType.INCREMENTAL,
                    full,
                    "inc-20261002",
                    Instant.parse("2026-10-02T02:00:00Z")
            );

            service.verify(incremental);

            System.out.println("Full state: " + full.state());
            System.out.println(
                    "Incremental state: " + incremental.state()
            );
            System.out.println(
                    "Full expired on 2026-10-20: " +
                            policy.expired(
                                    full.createdAt(),
                                    Instant.parse("2026-10-20T00:00:00Z")
                            )
            );

        } catch (Exception error) {
            System.err.println("Backup governance failure: "
                    + error.getMessage());
            System.exit(1);
        } finally {
            if (workspace != null) {
                try {
                    deleteRecursively(workspace);
                } catch (IOException ignored) {
                    System.err.println(
                            "Warning: temporary workspace cleanup failed"
                    );
                }
            }
        }
    }
}
