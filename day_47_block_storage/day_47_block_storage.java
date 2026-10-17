import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;

public class BlockStorageEnterpriseDemo {

    enum DiskType {
        HDD,
        SSD,
        NVME
    }

    enum AttachmentMode {
        READ_ONLY,
        READ_WRITE
    }

    enum VolumeState {
        AVAILABLE,
        ATTACHED
    }

    record PerformanceProfile(
            double latencyMs,
            double throughputMBps,
            long baselineIops
    ) {}

    record Snapshot(
            String id,
            String volumeId,
            double logicalSizeGiB,
            long changedBlocks,
            String parentSnapshotId
    ) {}

    static final class StorageException extends RuntimeException {
        StorageException(String message) {
            super(message);
        }
    }

    static final class BlockVolume {
        private final String id;
        private final double capacityGiB;
        private final DiskType type;
        private final String availabilityZone;
        private double usedGiB;
        private VolumeState state = VolumeState.AVAILABLE;
        private String attachedInstance;
        private final List<Snapshot> snapshots = new ArrayList<>();

        BlockVolume(
                String id,
                double capacityGiB,
                DiskType type,
                String availabilityZone
        ) {
            if (capacityGiB <= 0) {
                throw new StorageException(
                        "Volume capacity must be positive."
                );
            }

            this.id = Objects.requireNonNull(id);
            this.capacityGiB = capacityGiB;
            this.type = Objects.requireNonNull(type);
            this.availabilityZone = Objects.requireNonNull(
                    availabilityZone
            );
        }

        void write(double amountGiB) {
            if (amountGiB <= 0) {
                throw new StorageException(
                        "Write size must be positive."
                );
            }

            if (usedGiB + amountGiB > capacityGiB) {
                throw new StorageException(
                        "Volume capacity would be exceeded."
                );
            }

            usedGiB += amountGiB;
        }

        void attach(String instanceId) {
            if (state == VolumeState.ATTACHED) {
                throw new StorageException(
                        "Volume is already attached."
                );
            }

            state = VolumeState.ATTACHED;
            attachedInstance = instanceId;
        }

        void detach(String instanceId) {
            if (!instanceId.equals(attachedInstance)) {
                throw new StorageException(
                        "Volume is not attached to this instance."
                );
            }

            state = VolumeState.AVAILABLE;
            attachedInstance = null;
        }

        Snapshot createSnapshot(String snapshotId, long changedBlocks) {
            if (changedBlocks < 0) {
                throw new StorageException(
                        "Changed block count cannot be negative."
                );
            }

            String parent = snapshots.isEmpty()
                    ? null
                    : snapshots.get(snapshots.size() - 1).id();

            Snapshot snapshot = new Snapshot(
                    snapshotId,
                    id,
                    usedGiB,
                    changedBlocks,
                    parent
            );

            snapshots.add(snapshot);
            return snapshot;
        }

        String id() {
            return id;
        }

        double usedGiB() {
            return usedGiB;
        }

        double capacityGiB() {
            return capacityGiB;
        }

        DiskType type() {
            return type;
        }

        String availabilityZone() {
            return availabilityZone;
        }

        VolumeState state() {
            return state;
        }

        List<Snapshot> snapshots() {
            return Collections.unmodifiableList(snapshots);
        }
    }

    static final class ComputeInstance {
        private final String id;
        private final String availabilityZone;
        private final Map<String, AttachmentMode> attachments =
                new HashMap<>();

        ComputeInstance(String id, String availabilityZone) {
            this.id = Objects.requireNonNull(id);
            this.availabilityZone = Objects.requireNonNull(
                    availabilityZone
            );
        }

        void attach(BlockVolume volume, AttachmentMode mode) {
            if (!availabilityZone.equals(volume.availabilityZone())) {
                throw new StorageException(
                        "Volume and compute instance are in different zones."
                );
            }

            volume.attach(id);
            attachments.put(volume.id(), mode);
        }

        void detach(BlockVolume volume) {
            volume.detach(id);
            attachments.remove(volume.id());
        }
    }

    interface StoragePolicy {
        boolean allows(BlockVolume volume);

        String explanation();
    }

    static final class ProductionDatabasePolicy
            implements StoragePolicy {

        private final double minimumCapacityGiB;
        private final DiskType requiredType;

        ProductionDatabasePolicy(
                double minimumCapacityGiB,
                DiskType requiredType
        ) {
            this.minimumCapacityGiB = minimumCapacityGiB;
            this.requiredType = requiredType;
        }

        @Override
        public boolean allows(BlockVolume volume) {
            return volume.capacityGiB() >= minimumCapacityGiB
                    && volume.type() == requiredType;
        }

        @Override
        public String explanation() {
            return "Production database storage requires adequate capacity "
                    + "and NVMe-class media for latency-sensitive workloads.";
        }
    }

    static final class StorageService {
        private final Map<String, BlockVolume> volumes = new HashMap<>();
        private final Map<String, ComputeInstance> instances =
                new HashMap<>();
        private final Map<DiskType, PerformanceProfile> profiles =
                new EnumMap<>(DiskType.class);

        StorageService() {
            profiles.put(
                    DiskType.HDD,
                    new PerformanceProfile(8.0, 180.0, 150)
            );
            profiles.put(
                    DiskType.SSD,
                    new PerformanceProfile(0.8, 550.0, 50_000)
            );
            profiles.put(
                    DiskType.NVME,
                    new PerformanceProfile(0.15, 3500.0, 500_000)
            );
        }

        void register(BlockVolume volume) {
            if (volumes.putIfAbsent(volume.id(), volume) != null) {
                throw new StorageException(
                        "Duplicate volume: " + volume.id()
                );
            }
        }

        void register(ComputeInstance instance) {
            if (instances.putIfAbsent(instance.id, instance) != null) {
                throw new StorageException(
                        "Duplicate compute instance: " + instance.id
                );
            }
        }

        void attach(
                String volumeId,
                String instanceId,
                AttachmentMode mode
        ) {
            BlockVolume volume = requireVolume(volumeId);
            ComputeInstance instance = requireInstance(instanceId);
            instance.attach(volume, mode);
        }

        void detach(String volumeId, String instanceId) {
            BlockVolume volume = requireVolume(volumeId);
            ComputeInstance instance = requireInstance(instanceId);
            instance.detach(volume);
        }

        PerformanceProfile performance(BlockVolume volume) {
            return profiles.get(volume.type());
        }

        private BlockVolume requireVolume(String id) {
            BlockVolume volume = volumes.get(id);
            if (volume == null) {
                throw new StorageException(
                        "Unknown volume: " + id
                );
            }
            return volume;
        }

        private ComputeInstance requireInstance(String id) {
            ComputeInstance instance = instances.get(id);
            if (instance == null) {
                throw new StorageException(
                        "Unknown instance: " + id
                );
            }
            return instance;
        }
    }

    public static void main(String[] args) {
        StorageService storage = new StorageService();

        ComputeInstance databaseServer =
                new ComputeInstance("db-prod-01", "zone-a");
        ComputeInstance reportingServer =
                new ComputeInstance("reporting-01", "zone-a");

        BlockVolume databaseVolume = new BlockVolume(
                "db-data",
                500,
                DiskType.NVME,
                "zone-a"
        );

        BlockVolume reportingVolume = new BlockVolume(
                "reporting-data",
                1500,
                DiskType.SSD,
                "zone-a"
        );

        BlockVolume archiveVolume = new BlockVolume(
                "long-term-archive",
                5000,
                DiskType.HDD,
                "zone-a"
        );

        storage.register(databaseServer);
        storage.register(reportingServer);
        storage.register(databaseVolume);
        storage.register(reportingVolume);
        storage.register(archiveVolume);

        StoragePolicy databasePolicy =
                new ProductionDatabasePolicy(250, DiskType.NVME);

        if (!databasePolicy.allows(databaseVolume)) {
            throw new StorageException(databasePolicy.explanation());
        }

        storage.attach(
                "db-data",
                "db-prod-01",
                AttachmentMode.READ_WRITE
        );

        storage.attach(
                "reporting-data",
                "reporting-01",
                AttachmentMode.READ_WRITE
        );

        databaseVolume.write(185);
        reportingVolume.write(430);
        archiveVolume.write(2100);

        Snapshot beforeMaintenance =
                databaseVolume.createSnapshot(
                        "db-before-maintenance",
                        47_360
                );

        databaseVolume.write(32);

        Snapshot afterMaintenance =
                databaseVolume.createSnapshot(
                        "db-after-maintenance",
                        8_192
                );

        System.out.println("Enterprise block-storage scenario");
        System.out.println(
                "Database volume: "
                        + databaseVolume.usedGiB()
                        + "/"
                        + databaseVolume.capacityGiB()
                        + " GiB"
        );

        PerformanceProfile profile =
                storage.performance(databaseVolume);

        System.out.println(
                "Database media: " + databaseVolume.type()
                        + ", latency=" + profile.latencyMs()
                        + " ms, throughput="
                        + profile.throughputMBps()
                        + " MB/s"
        );

        System.out.println(
                "First snapshot parent: "
                        + Optional.ofNullable(
                                beforeMaintenance.parentSnapshotId()
                        ).orElse("none")
        );

        System.out.println(
                "Second snapshot parent: "
                        + Optional.ofNullable(
                                afterMaintenance.parentSnapshotId()
                        ).orElse("none")
        );

        try {
            storage.attach(
                    "db-data",
                    "reporting-01",
                    AttachmentMode.READ_ONLY
            );
        } catch (StorageException exception) {
            System.out.println(
                    "Rejected conflicting attachment: "
                            + exception.getMessage()
            );
        }

        try {
            databaseVolume.write(400);
        } catch (StorageException exception) {
            System.out.println(
                    "Rejected unsafe write: "
                            + exception.getMessage()
            );
        }

        storage.detach("db-data", "db-prod-01");

        System.out.println(
                "Volume state after detachment: "
                        + databaseVolume.state()
        );

        System.out.println(
                "Snapshots retained: "
                        + databaseVolume.snapshots().size()
        );
    }
}
