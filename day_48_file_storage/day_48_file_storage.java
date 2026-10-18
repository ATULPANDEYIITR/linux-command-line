import java.time.Instant;
import java.util.ArrayList;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;

public class FileStorageEnterpriseDemo {

    enum StorageType {
        SHARED_FILESYSTEM,
        NETWORK_FILE_STORAGE,
        DISTRIBUTED_STORAGE
    }

    enum NodeState {
        ONLINE,
        OFFLINE
    }

    record FileMetadata(
        String path,
        String owner,
        long size,
        String checksum,
        int version,
        Instant modifiedAt
    ) {}

    record StoredObject(
        FileMetadata metadata,
        byte[] content
    ) {
        StoredObject {
            content = content.clone();
        }

        @Override
        public byte[] content() {
            return content.clone();
        }
    }

    static class StorageException extends RuntimeException {
        StorageException(String message) {
            super(message);
        }
    }

    static class CapacityException extends StorageException {
        CapacityException(String message) {
            super(message);
        }
    }

    static class ConsistencyException extends StorageException {
        ConsistencyException(String message) {
            super(message);
        }
    }

    static class SharedFilesystemService {
        private final Map<String, StoredObject> files = new HashMap<>();
        private final long capacityBytes;
        private long usedBytes;

        SharedFilesystemService(long capacityBytes) {
            if (capacityBytes <= 0) {
                throw new IllegalArgumentException(
                    "Capacity must be positive"
                );
            }
            this.capacityBytes = capacityBytes;
        }

        private static String checksum(byte[] data) {
            long value = 1125899906842597L;

            for (byte item : data) {
                value = 31 * value + item;
            }

            return Long.toUnsignedString(value, 16);
        }

        void write(
            String path,
            String owner,
            byte[] content
        ) {
            Objects.requireNonNull(path);
            Objects.requireNonNull(owner);
            Objects.requireNonNull(content);

            StoredObject previous = files.get(path);
            long oldSize =
                previous == null ? 0 : previous.metadata().size();

            long proposedUsage =
                usedBytes - oldSize + content.length;

            if (proposedUsage > capacityBytes) {
                throw new CapacityException(
                    "Filesystem capacity exceeded"
                );
            }

            int version =
                previous == null
                    ? 1
                    : previous.metadata().version() + 1;

            FileMetadata metadata = new FileMetadata(
                path,
                owner,
                content.length,
                checksum(content),
                version,
                Instant.now()
            );

            files.put(
                path,
                new StoredObject(metadata, content)
            );

            usedBytes = proposedUsage;
        }

        Optional<StoredObject> read(String path) {
            return Optional.ofNullable(files.get(path));
        }
    }

    static final class NetworkFileClient {
        private final SharedFilesystemService server;
        private final String hostName;
        private boolean mounted;

        NetworkFileClient(
            SharedFilesystemService server,
            String hostName
        ) {
            this.server = server;
            this.hostName = hostName;
        }

        void mount() {
            mounted = true;
            System.out.println(hostName + ": mounted network share");
        }

        private void requireMount() {
            if (!mounted) {
                throw new StorageException(
                    hostName + ": network share is unavailable"
                );
            }
        }

        void write(
            String path,
            String owner,
            byte[] content
        ) {
            requireMount();
            server.write(path, owner, content);
        }

        byte[] read(String path) {
            requireMount();

            return server.read(path)
                .orElseThrow(() ->
                    new StorageException(
                        "Remote file does not exist: " + path
                    )
                )
                .content();
        }
    }

    static final class StorageNode {
        private final String id;
        private NodeState state = NodeState.ONLINE;
        private final Map<String, StoredObject> objects =
            new HashMap<>();

        StorageNode(String id) {
            this.id = id;
        }

        String id() {
            return id;
        }

        boolean online() {
            return state == NodeState.ONLINE;
        }

        void setState(NodeState state) {
            this.state = state;
        }

        void store(String key, StoredObject object) {
            if (!online()) {
                throw new StorageException(
                    "Cannot write to offline node " + id
                );
            }

            objects.put(key, object);
        }

        Optional<StoredObject> get(String key) {
            return Optional.ofNullable(objects.get(key));
        }
    }

    static final class DistributedStorageService {
        private final List<StorageNode> nodes;
        private final int replicationFactor;

        DistributedStorageService(
            List<String> nodeIds,
            int replicationFactor
        ) {
            if (nodeIds.isEmpty()) {
                throw new IllegalArgumentException(
                    "At least one node is required"
                );
            }

            if (
                replicationFactor < 1 ||
                replicationFactor > nodeIds.size()
            ) {
                throw new IllegalArgumentException(
                    "Invalid replication factor"
                );
            }

            this.nodes = nodeIds.stream()
                .map(StorageNode::new)
                .toList();

            this.replicationFactor = replicationFactor;
        }

        private static String checksum(byte[] content) {
            long value = 1469598103934665603L;

            for (byte item : content) {
                value ^= item;
                value *= 1099511628211L;
            }

            return Long.toUnsignedString(value, 16);
        }

        void put(
            String key,
            String owner,
            byte[] content
        ) {
            List<StorageNode> healthy = nodes.stream()
                .filter(StorageNode::online)
                .toList();

            if (healthy.size() < replicationFactor) {
                throw new StorageException(
                    "Insufficient healthy nodes for replication"
                );
            }

            FileMetadata metadata = new FileMetadata(
                key,
                owner,
                content.length,
                checksum(content),
                1,
                Instant.now()
            );

            StoredObject object =
                new StoredObject(metadata, content);

            healthy.stream()
                .limit(replicationFactor)
                .forEach(node -> node.store(key, object));
        }

        byte[] readVerified(String key) {
            List<StoredObject> copies = nodes.stream()
                .filter(StorageNode::online)
                .map(node -> node.get(key))
                .flatMap(Optional::stream)
                .toList();

            if (copies.isEmpty()) {
                throw new StorageException(
                    "No healthy replica contains " + key
                );
            }

            String expected =
                checksum(copies.get(0).content());

            for (StoredObject object : copies) {
                if (
                    !expected.equals(
                        object.metadata().checksum()
                    ) ||
                    !expected.equals(
                        checksum(object.content())
                    )
                ) {
                    throw new ConsistencyException(
                        "Replica integrity failure for " + key
                    );
                }
            }

            return copies.get(0).content();
        }

        void setNodeState(
            String nodeId,
            NodeState state
        ) {
            StorageNode node = nodes.stream()
                .filter(candidate ->
                    candidate.id().equals(nodeId)
                )
                .findFirst()
                .orElseThrow(() ->
                    new StorageException(
                        "Unknown storage node " + nodeId
                    )
                );

            node.setState(state);
        }

        Map<String, Boolean> placement(String key) {
            Map<String, Boolean> result = new HashMap<>();

            for (StorageNode node : nodes) {
                result.put(
                    node.id(),
                    node.get(key).isPresent()
                );
            }

            return result;
        }

        void repair(String key) {
            byte[] trustedContent = readVerified(key);
            String trustedChecksum = checksum(trustedContent);

            FileMetadata metadata = new FileMetadata(
                key,
                "repair-service",
                trustedContent.length,
                trustedChecksum,
                2,
                Instant.now()
            );

            StoredObject repaired =
                new StoredObject(metadata, trustedContent);

            for (StorageNode node : nodes) {
                if (node.online()) {
                    node.store(key, repaired);
                }
            }
        }
    }

    record StoragePolicy(
        StorageType type,
        boolean sharedNamespace,
        boolean requiresNetwork,
        boolean usesReplication,
        String rationale
    ) {}

    static StoragePolicy selectPolicy(
        boolean sharedFiles,
        boolean remoteHosts,
        boolean nodeFailureTolerance
    ) {
        if (nodeFailureTolerance) {
            return new StoragePolicy(
                StorageType.DISTRIBUTED_STORAGE,
                false,
                true,
                true,
                "Replication is required for node-level failure tolerance"
            );
        }

        if (remoteHosts || sharedFiles) {
            return new StoragePolicy(
                StorageType.NETWORK_FILE_STORAGE,
                true,
                true,
                false,
                "Multiple hosts require one shared file namespace"
            );
        }

        return new StoragePolicy(
            StorageType.SHARED_FILESYSTEM,
            true,
            false,
            false,
            "A local filesystem namespace satisfies the workload"
        );
    }

    public static void main(String[] args) {
        System.out.println(
            "=== Enterprise File Storage Model ==="
        );

        SharedFilesystemService shared =
            new SharedFilesystemService(100_000);

        NetworkFileClient analytics =
            new NetworkFileClient(
                shared,
                "analytics-host"
            );

        NetworkFileClient application =
            new NetworkFileClient(
                shared,
                "application-host"
            );

        try {
            analytics.read("reports/monthly.csv");
        } catch (StorageException exception) {
            System.out.println(
                "Before mount: " + exception.getMessage()
            );
        }

        analytics.mount();
        application.mount();

        analytics.write(
            "reports/monthly.csv",
            "finance",
            "month,revenue\n2026-10,163500\n"
                .getBytes()
        );

        System.out.println(
            "Remote client reads: "
                + new String(
                    application.read("reports/monthly.csv")
                )
        );

        DistributedStorageService distributed =
            new DistributedStorageService(
                List.of("node-a", "node-b", "node-c"),
                2
            );

        String objectKey =
            "datasets/customer-events/2026-10.json";

        distributed.put(
            objectKey,
            "analytics-service",
            "{\"event\":\"purchase\",\"amount\":2499}"
                .getBytes()
        );

        System.out.println(
            "Replica placement: "
                + distributed.placement(objectKey)
        );

        distributed.setNodeState(
            "node-a",
            NodeState.OFFLINE
        );

        System.out.println(
            "Read with node-a offline: "
                + new String(
                    distributed.readVerified(objectKey)
                )
        );

        distributed.setNodeState(
            "node-a",
            NodeState.ONLINE
        );

        StoragePolicy policy = selectPolicy(
            true,
            true,
            false
        );

        System.out.println(
            "Selected storage model: "
                + policy.type()
        );

        System.out.println(
            "Policy rationale: "
                + policy.rationale()
        );

        try {
            new SharedFilesystemService(4)
                .write(
                    "large.bin",
                    "application",
                    "123456".getBytes()
                );
        } catch (CapacityException exception) {
            System.out.println(
                "Capacity policy rejected write: "
                    + exception.getMessage()
            );
        }
    }
}
