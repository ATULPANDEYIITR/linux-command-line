import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Java 17 enterprise-style compute and storage architecture model.
 *
 * Compile: javac CloudArchitecture.java
 * Run:     java CloudArchitecture
 */
public class CloudArchitecture {

    enum InstanceState {
        RUNNING, STOPPED, UNHEALTHY
    }

    enum ObjectState {
        ACTIVE, DELETED
    }

    enum BackupState {
        COMPLETED, FAILED
    }

    static class ArchitectureException extends RuntimeException {
        ArchitectureException(String message) {
            super(message);
        }
    }

    static final class ValidationException extends ArchitectureException {
        ValidationException(String message) {
            super(message);
        }
    }

    static final class CapacityException extends ArchitectureException {
        CapacityException(String message) {
            super(message);
        }
    }

    static final class IntegrityException extends ArchitectureException {
        IntegrityException(String message) {
            super(message);
        }
    }

    record ComputeInstance(
            String id,
            String zone,
            int capacity,
            int activeRequests,
            InstanceState state) {

        ComputeInstance {
            if (id == null || id.isBlank() || zone == null || zone.isBlank()) {
                throw new ValidationException("Instance ID and zone are required.");
            }
            if (capacity < 1 || activeRequests < 0 || activeRequests > capacity) {
                throw new ValidationException("Invalid compute capacity or request count.");
            }
            Objects.requireNonNull(state, "Instance state is required.");
        }

        double utilization() {
            return (double) activeRequests / capacity;
        }

        ComputeInstance withActiveRequests(int count) {
            return new ComputeInstance(id, zone, capacity, count, state);
        }

        ComputeInstance withState(InstanceState nextState) {
            return new ComputeInstance(id, zone, capacity, activeRequests, nextState);
        }
    }

    record StoredObject(
            String key,
            int version,
            String contentBase64,
            String checksum,
            ObjectState state,
            Instant createdAt) {

        StoredObject {
            validateKey(key);
            if (version < 1) {
                throw new ValidationException("Object version must be positive.");
            }
            Objects.requireNonNull(contentBase64);
            Objects.requireNonNull(checksum);
            Objects.requireNonNull(state);
            Objects.requireNonNull(createdAt);
        }

        byte[] content() {
            return Base64.getDecoder().decode(contentBase64);
        }

        static StoredObject create(String key, int version, byte[] content) {
            return new StoredObject(
                    key,
                    version,
                    Base64.getEncoder().encodeToString(content),
                    sha256(content),
                    ObjectState.ACTIVE,
                    Instant.now());
        }
    }

    record Backup(
            String id,
            Instant createdAt,
            Map<String, Integer> manifest,
            Map<String, String> contentByKey,
            BackupState state,
            String checksum) {

        Backup {
            manifest = Map.copyOf(manifest);
            contentByKey = Map.copyOf(contentByKey);
            Objects.requireNonNull(state);
        }
    }

    private static void validateKey(String key) {
        if (key == null || key.isBlank() || key.startsWith("/")
                || key.contains("\\")
                || List.of(key.split("/", -1)).stream()
                    .anyMatch(part -> part.equals("..") || part.isEmpty())) {
            throw new ValidationException("Object key must be a safe relative path.");
        }
    }

    private static String sha256(byte[] data) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(data);
            StringBuilder result = new StringBuilder();
            for (byte value : digest) {
                result.append(String.format("%02x", value & 0xff));
            }
            return result.toString();
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException("SHA-256 is unavailable.", impossible);
        }
    }

    private static String backupChecksum(
            Map<String, Integer> manifest,
            Map<String, String> contentByKey) {

        StringBuilder canonical = new StringBuilder();
        manifest.keySet().stream().sorted().forEach(key ->
                canonical.append(key.length()).append(':').append(key)
                        .append(':').append(manifest.get(key))
                        .append(':').append(contentByKey.get(key)).append('\n'));

        return sha256(canonical.toString().getBytes(StandardCharsets.UTF_8));
    }

    static final class ObjectStore {
        private final Map<String, List<StoredObject>> objects = new HashMap<>();
        private final int maximumBytes;

        ObjectStore(int maximumBytes) {
            if (maximumBytes < 1) {
                throw new ValidationException("Object size limit must be positive.");
            }
            this.maximumBytes = maximumBytes;
        }

        synchronized StoredObject put(String key, byte[] content) {
            validateKey(key);
            Objects.requireNonNull(content, "Object content is required.");
            if (content.length > maximumBytes) {
                throw new ValidationException("Object exceeds size limit.");
            }

            List<StoredObject> history =
                    objects.computeIfAbsent(key, ignored -> new ArrayList<>());

            StoredObject object = StoredObject.create(
                    key, history.size() + 1, content.clone());
            history.add(object);
            return object;
        }

        synchronized StoredObject get(String key, Integer version) {
            List<StoredObject> history = objects.getOrDefault(key, List.of());

            if (version == null) {
                for (int index = history.size() - 1; index >= 0; index--) {
                    StoredObject candidate = history.get(index);
                    if (candidate.state() == ObjectState.ACTIVE) {
                        return candidate;
                    }
                    break;
                }
            } else if (version >= 1 && version <= history.size()) {
                StoredObject candidate = history.get(version - 1);
                if (candidate.state() == ObjectState.ACTIVE) return candidate;
            }

            throw new ArchitectureException("Active object not found: " + key);
        }

        synchronized void delete(String key) {
            StoredObject object = get(key, null);
            List<StoredObject> history = objects.get(key);
            history.set(history.size() - 1, new StoredObject(
                    object.key(), object.version(), object.contentBase64(),
                    object.checksum(), ObjectState.DELETED, object.createdAt()));
        }

        synchronized Backup createBackup() {
            Map<String, Integer> manifest = new HashMap<>();
            Map<String, String> data = new HashMap<>();

            objects.forEach((key, history) -> {
                if (!history.isEmpty()) {
                    StoredObject current = history.get(history.size() - 1);
                    if (current.state() == ObjectState.ACTIVE) {
                        manifest.put(key, current.version());
                        data.put(key, current.contentBase64());
                    }
                }
            });

            return new Backup(
                    UUID.randomUUID().toString(),
                    Instant.now(),
                    manifest,
                    data,
                    BackupState.COMPLETED,
                    backupChecksum(manifest, data));
        }

        synchronized void restore(Backup backup) {
            if (backup.state() != BackupState.COMPLETED) {
                throw new IntegrityException("Cannot restore an incomplete backup.");
            }
            if (!backup.manifest().keySet().equals(backup.contentByKey().keySet())
                    || !backup.checksum().equals(
                            backupChecksum(backup.manifest(), backup.contentByKey()))) {
                throw new IntegrityException("Backup manifest or checksum is invalid.");
            }

            Map<String, List<StoredObject>> replacement = new HashMap<>();
            backup.manifest().forEach((key, version) -> {
                validateKey(key);
                byte[] content;
                try {
                    content = Base64.getDecoder().decode(backup.contentByKey().get(key));
                } catch (IllegalArgumentException error) {
                    throw new IntegrityException("Invalid backup content encoding.");
                }
                if (content.length > maximumBytes || version < 1) {
                    throw new IntegrityException("Backup object violates storage limits.");
                }
                replacement.put(key, new ArrayList<>(List.of(
                        StoredObject.create(key, version, content))));
            });

            // Publish a complete replacement only after every object passes validation.
            objects.clear();
            objects.putAll(replacement);
        }
    }

    static final class LoadBalancer {
        private final Map<String, ComputeInstance> instances = new HashMap<>();

        LoadBalancer(List<ComputeInstance> initialInstances) {
            for (ComputeInstance instance : initialInstances) {
                if (instances.putIfAbsent(instance.id(), instance) != null) {
                    throw new ValidationException("Duplicate instance ID.");
                }
            }
        }

        synchronized String acquire() {
            ComputeInstance selected = instances.values().stream()
                    .filter(instance -> instance.state() == InstanceState.RUNNING)
                    .filter(instance -> instance.activeRequests() < instance.capacity())
                    .min(Comparator.comparingDouble(ComputeInstance::utilization)
                            .thenComparing(ComputeInstance::id))
                    .orElseThrow(() -> new CapacityException(
                            "No healthy instance has available capacity."));

            instances.put(
                    selected.id(),
                    selected.withActiveRequests(selected.activeRequests() + 1));
            return selected.id();
        }

        synchronized void release(String id) {
            ComputeInstance instance = instances.get(id);
            if (instance == null || instance.activeRequests() == 0) {
                throw new ValidationException("Invalid connection release.");
            }
            instances.put(id, instance.withActiveRequests(instance.activeRequests() - 1));
        }

        synchronized void setHealth(String id, boolean healthy) {
            ComputeInstance instance = instances.get(id);
            if (instance == null) throw new ValidationException("Unknown instance.");

            instances.put(id, instance.withState(
                    healthy ? InstanceState.RUNNING : InstanceState.UNHEALTHY));
        }

        synchronized List<ComputeInstance> report() {
            return instances.values().stream()
                    .sorted(Comparator.comparing(ComputeInstance::id))
                    .toList();
        }
    }

    record PolicyResult(boolean eligible, List<String> violations) {
        PolicyResult {
            violations = List.copyOf(violations);
        }
    }

    interface ArchitectureRule {
        List<String> validate(
                List<ComputeInstance> instances,
                List<Backup> backups);
    }

    static final class ZoneDiversityRule implements ArchitectureRule {
        private final int minimumZones;

        ZoneDiversityRule(int minimumZones) {
            if (minimumZones < 1) {
                throw new ValidationException("Minimum zone count must be positive.");
            }
            this.minimumZones = minimumZones;
        }

        @Override
        public List<String> validate(
                List<ComputeInstance> instances,
                List<Backup> backups) {

            Set<String> zones = new HashSet<>();
            instances.stream()
                    .filter(i -> i.state() == InstanceState.RUNNING)
                    .forEach(i -> zones.add(i.zone()));

            return zones.size() < minimumZones
                    ? List.of("Insufficient availability-zone diversity.")
                    : List.of();
        }
    }

    static final class BackupRule implements ArchitectureRule {
        @Override
        public List<String> validate(
                List<ComputeInstance> instances,
                List<Backup> backups) {

            return backups.stream().noneMatch(
                    backup -> backup.state() == BackupState.COMPLETED)
                    ? List.of("A completed backup is required.")
                    : List.of();
        }
    }

    static final class GovernanceService {
        private final List<ArchitectureRule> rules;

        GovernanceService(List<ArchitectureRule> rules) {
            this.rules = List.copyOf(rules);
        }

        PolicyResult evaluate(
                List<ComputeInstance> instances,
                List<Backup> backups) {

            List<String> violations = new ArrayList<>();
            for (ArchitectureRule rule : rules) {
                violations.addAll(rule.validate(instances, backups));
            }

            if (instances.stream().noneMatch(
                    i -> i.state() == InstanceState.RUNNING)) {
                violations.add("At least one running instance is required.");
            }

            return new PolicyResult(violations.isEmpty(), violations);
        }
    }

    static CompletableFuture<String> serveRequest(
            LoadBalancer balancer,
            ObjectStore store,
            int requestNumber) {

        return CompletableFuture.supplyAsync(() -> {
            String instanceId = balancer.acquire();
            try {
                StoredObject configuration = store.get("config/service.json", null);
                return "request-" + requestNumber
                        + " served by " + instanceId
                        + " checksum=" + configuration.checksum();
            } finally {
                balancer.release(instanceId);
            }
        });
    }

    static void writeBackupReport(Backup backup) throws IOException {
        Path report = Files.createTempFile("architecture-report-", ".json");
        try {
            String json = """
                    {
                      "backupId": "%s",
                      "createdAt": "%s",
                      "state": "%s",
                      "objectCount": %d,
                      "checksum": "%s"
                    }
                    """.formatted(
                    backup.id(),
                    backup.createdAt(),
                    backup.state(),
                    backup.manifest().size(),
                    backup.checksum());

            Files.writeString(report, json, StandardCharsets.UTF_8);
            System.out.println("Backup report created: " + report.getFileName());
        } finally {
            Files.deleteIfExists(report);
        }
    }

    public static void main(String[] args) {
        try {
            ObjectStore store = new ObjectStore(4096);
            byte[] original = """
                    {"service":"inventory","revision":1}
                    """.strip().getBytes(StandardCharsets.UTF_8);

            store.put("config/service.json", original);
            store.put("reports/daily.txt", "Daily inventory report".getBytes(
                    StandardCharsets.UTF_8));

            Backup backup = store.createBackup();

            LoadBalancer balancer = new LoadBalancer(List.of(
                    new ComputeInstance("vm-a", "zone-a", 2, 0, InstanceState.RUNNING),
                    new ComputeInstance("vm-b", "zone-b", 3, 0, InstanceState.RUNNING),
                    new ComputeInstance("vm-c", "zone-c", 1, 0, InstanceState.RUNNING)));

            GovernanceService governance = new GovernanceService(List.of(
                    new ZoneDiversityRule(2),
                    new BackupRule()));

            PolicyResult initial = governance.evaluate(balancer.report(), List.of(backup));
            if (!initial.eligible()) {
                throw new ArchitectureException(initial.violations().toString());
            }

            List<CompletableFuture<String>> requests = new ArrayList<>();
            for (int i = 1; i <= 8; i++) {
                requests.add(serveRequest(balancer, store, i));
            }

            CompletableFuture.allOf(requests.toArray(CompletableFuture[]::new)).join();
            requests.forEach(request -> System.out.println(request.join()));

            store.put(
                    "config/service.json",
                    "{\"service\":\"inventory\",\"revision\":2}"
                            .getBytes(StandardCharsets.UTF_8));

            if (!store.get("config/service.json", 1).checksum().equals(
                    sha256(original))) {
                throw new IntegrityException("Historical object version changed.");
            }

            store.delete("reports/daily.txt");
            try {
                store.get("reports/daily.txt", null);
            } catch (ArchitectureException expected) {
                System.out.println("Deleted object is hidden from current reads.");
            }

            store.restore(backup);
            if (!store.get("config/service.json", null).checksum().equals(
                    sha256(original))) {
                throw new IntegrityException("Restored content does not match backup.");
            }

            balancer.setHealth("vm-a", false);
            PolicyResult updated = governance.evaluate(balancer.report(), List.of(backup));
            System.out.println("Policy after health change: " + updated);

            writeBackupReport(backup);

            try {
                store.put("../secrets.txt", "sensitive".getBytes(StandardCharsets.UTF_8));
            } catch (ValidationException expected) {
                System.out.println("Unsafe object key rejected.");
            }

            try {
                new LoadBalancer(List.of()).acquire();
            } catch (CapacityException expected) {
                System.out.println("Empty compute pool correctly rejected a request.");
            }

            System.out.println("Architecture simulation completed successfully.");
        } catch (CompletionException error) {
            System.err.println("Asynchronous request failed: " + error.getCause());
            System.exitCode = 1;
        } catch (Exception error) {
            System.err.println("Architecture failure: " + error.getMessage());
            System.exitCode = 1;
        }
    }
}
