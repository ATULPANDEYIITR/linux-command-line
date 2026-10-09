import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.TreeMap;

public class GeographicResilience {
    enum Health {
        HEALTHY, FAILED
    }

    enum Residency {
        INDIA, APAC, GLOBAL
    }

    enum FailureDomain {
        ZONE, REGION
    }

    record RecoveryObjective(int rtoMinutes, int rpoMinutes) {
        RecoveryObjective {
            if (rtoMinutes < 0 || rpoMinutes < 0) {
                throw new IllegalArgumentException("RTO and RPO cannot be negative.");
            }
        }
    }

    record RecoveryMeasurement(
            int detectionMinutes,
            int failoverMinutes,
            int replicationLagMinutes,
            boolean tested
    ) {
        RecoveryMeasurement {
            if (detectionMinutes < 0 || failoverMinutes < 0 ||
                    replicationLagMinutes < 0) {
                throw new IllegalArgumentException("Recovery measurements cannot be negative.");
            }
        }

        List<String> evaluate(RecoveryObjective objective) {
            List<String> violations = new ArrayList<>();
            int actualRto = detectionMinutes + failoverMinutes;

            if (actualRto > objective.rtoMinutes()) {
                violations.add("RTO exceeded: " + actualRto + " minutes.");
            }
            if (replicationLagMinutes > objective.rpoMinutes()) {
                violations.add("RPO exceeded: " + replicationLagMinutes + " minutes.");
            }
            if (!tested) {
                violations.add("Recovery procedure has not been tested.");
            }
            return List.copyOf(violations);
        }
    }

    static final class Region {
        private final String id;
        private final Residency residency;
        private final Set<String> zoneIds = new HashSet<>();
        private Health health = Health.HEALTHY;

        Region(String id, Residency residency) {
            this.id = Objects.requireNonNull(id);
            this.residency = Objects.requireNonNull(residency);
            if (id.isBlank()) throw new IllegalArgumentException("Region ID is required.");
        }

        String id() { return id; }
        Residency residency() { return residency; }
        Health health() { return health; }
    }

    static final class Zone {
        private final String id;
        private final String regionId;
        private final int capacity;
        private final double latencyMs;
        private final Map<String, Integer> reservations = new HashMap<>();
        private Health health = Health.HEALTHY;

        Zone(String id, String regionId, int capacity, double latencyMs) {
            this.id = Objects.requireNonNull(id);
            this.regionId = Objects.requireNonNull(regionId);

            if (id.isBlank() || regionId.isBlank() ||
                    capacity < 0 || latencyMs < 0) {
                throw new IllegalArgumentException("Invalid zone configuration.");
            }

            this.capacity = capacity;
            this.latencyMs = latencyMs;
        }

        String id() { return id; }
        String regionId() { return regionId; }
        double latencyMs() { return latencyMs; }
        Health health() { return health; }

        int usedCapacity() {
            return reservations.values().stream().mapToInt(Integer::intValue).sum();
        }

        int freeCapacity() {
            return health == Health.HEALTHY ? capacity - usedCapacity() : 0;
        }

        void reserve(String workloadId, int units) {
            if (health != Health.HEALTHY) {
                throw new IllegalStateException("Cannot reserve capacity in a failed zone.");
            }
            if (units <= 0 || units > freeCapacity()) {
                throw new IllegalStateException("Capacity reservation is invalid.");
            }
            reservations.merge(workloadId, units, Integer::sum);
        }

        void release(String workloadId) {
            reservations.remove(workloadId);
        }
    }

    static final class Workload {
        private final String id;
        private final int requiredUnits;
        private final int minimumZones;
        private final double maximumLatencyMs;
        private final Residency residency;
        private final Map<String, Integer> placement = new TreeMap<>();

        Workload(
                String id,
                int requiredUnits,
                int minimumZones,
                double maximumLatencyMs,
                Residency residency
        ) {
            if (id == null || id.isBlank() || requiredUnits <= 0 ||
                    minimumZones <= 0 || maximumLatencyMs < 0) {
                throw new IllegalArgumentException("Invalid workload policy.");
            }

            this.id = id;
            this.requiredUnits = requiredUnits;
            this.minimumZones = minimumZones;
            this.maximumLatencyMs = maximumLatencyMs;
            this.residency = Objects.requireNonNull(residency);
        }

        String id() { return id; }
        int requiredUnits() { return requiredUnits; }
        int minimumZones() { return minimumZones; }
        Map<String, Integer> placement() { return Map.copyOf(placement); }
    }

    record PlacementReport(
            int survivingUnits,
            int survivingZones,
            boolean capacitySatisfied,
            boolean zoneSpreadSatisfied
    ) {}

    static final class InfrastructureService {
        private final Map<String, Region> regions = new TreeMap<>();
        private final Map<String, Zone> zones = new TreeMap<>();

        void registerRegion(Region region) {
            if (regions.putIfAbsent(region.id(), region) != null) {
                throw new IllegalArgumentException("Duplicate region: " + region.id());
            }
        }

        void registerZone(Zone zone) {
            Region region = regions.get(zone.regionId());
            if (region == null) {
                throw new IllegalArgumentException("Zone references an unknown region.");
            }
            if (region.residency() == Residency.GLOBAL ||
                    (region.residency() != Residency.GLOBAL &&
                     region.residency() != zoneResidency(zone))) {
                throw new IllegalArgumentException("Region and zone residency conflict.");
            }
            if (zones.putIfAbsent(zone.id(), zone) != null) {
                throw new IllegalArgumentException("Duplicate zone: " + zone.id());
            }
            region.zoneIds.add(zone.id());
        }

        private Residency zoneResidency(Zone zone) {
            return regions.get(zone.regionId()).residency();
        }

        void deploy(Workload workload, Set<String> allowedRegions) {
            if (!workload.placement.isEmpty()) {
                throw new IllegalStateException("Workload is already deployed.");
            }

            List<Zone> candidates = zones.values().stream()
                    .filter(zone -> allowedRegions.contains(zone.regionId()))
                    .filter(zone -> zone.health() == Health.HEALTHY)
                    .filter(zone -> regions.get(zone.regionId()).health() == Health.HEALTHY)
                    .filter(zone -> regions.get(zone.regionId()).residency() == workload.residency)
                    .filter(zone -> zone.latencyMs() <= workload.maximumLatencyMs)
                    .sorted(Comparator.comparingDouble(Zone::latencyMs)
                            .thenComparing(Comparator.comparingInt(Zone::freeCapacity).reversed())
                            .thenComparing(Zone::id))
                    .toList();

            if (candidates.size() < workload.minimumZones) {
                throw new IllegalStateException("Not enough eligible zones.");
            }

            Map<String, Integer> planned = new TreeMap<>();
            int remaining = workload.requiredUnits;

            for (Zone zone : candidates) {
                if (planned.size() >= workload.minimumZones || remaining == 0) break;
                planned.put(zone.id(), 1);
                remaining--;
            }

            for (Zone zone : candidates) {
                if (remaining == 0) break;
                int current = planned.getOrDefault(zone.id(), 0);
                int addition = Math.min(remaining, zone.freeCapacity() - current);
                if (addition > 0) {
                    planned.put(zone.id(), current + addition);
                    remaining -= addition;
                }
            }

            if (remaining > 0) {
                throw new IllegalStateException("Eligible capacity is insufficient.");
            }

            // Validate before committing reservations to avoid partial placement.
            for (Map.Entry<String, Integer> entry : planned.entrySet()) {
                Zone zone = zones.get(entry.getKey());
                if (zone.health() != Health.HEALTHY ||
                        entry.getValue() > zone.freeCapacity()) {
                    throw new IllegalStateException("Placement changed during validation.");
                }
            }

            List<Zone> reserved = new ArrayList<>();
            try {
                for (Map.Entry<String, Integer> entry : planned.entrySet()) {
                    Zone zone = zones.get(entry.getKey());
                    zone.reserve(workload.id(), entry.getValue());
                    reserved.add(zone);
                }
                workload.placement.putAll(planned);
            } catch (RuntimeException exception) {
                reserved.forEach(zone -> zone.release(workload.id()));
                throw exception;
            }
        }

        void failZone(String zoneId) {
            Zone zone = requireZone(zoneId);
            zone.health = Health.FAILED;
        }

        void recoverZone(String zoneId) {
            Zone zone = requireZone(zoneId);
            zone.health = Health.HEALTHY;
        }

        void failRegion(String regionId) {
            Region region = requireRegion(regionId);
            region.health = Health.FAILED;
            region.zoneIds.forEach(id -> zones.get(id).health = Health.FAILED);
        }

        void recoverRegion(String regionId) {
            Region region = requireRegion(regionId);
            region.health = Health.HEALTHY;
            region.zoneIds.forEach(id -> zones.get(id).health = Health.HEALTHY);
        }

        private Zone requireZone(String id) {
            Zone zone = zones.get(id);
            if (zone == null) throw new IllegalArgumentException("Unknown zone: " + id);
            return zone;
        }

        private Region requireRegion(String id) {
            Region region = regions.get(id);
            if (region == null) throw new IllegalArgumentException("Unknown region: " + id);
            return region;
        }

        PlacementReport evaluate(Workload workload) {
            int units = 0;
            int count = 0;

            for (Map.Entry<String, Integer> entry : workload.placement.entrySet()) {
                if (zones.get(entry.getKey()).health() == Health.HEALTHY) {
                    units += entry.getValue();
                    if (entry.getValue() > 0) count++;
                }
            }

            return new PlacementReport(
                    units,
                    count,
                    units >= workload.requiredUnits(),
                    count >= workload.minimumZones()
            );
        }

        void printInventory() {
            for (Region region : regions.values()) {
                System.out.printf("Region %s: %s%n", region.id(), region.health());
                for (String zoneId : region.zoneIds) {
                    Zone zone = zones.get(zoneId);
                    System.out.printf(
                            "  %s: %s, free=%d/%d, latency=%.1f ms%n",
                            zone.id(),
                            zone.health(),
                            zone.freeCapacity(),
                            zone.capacity,
                            zone.latencyMs()
                    );
                }
            }
        }
    }

    public static void main(String[] args) {
        InfrastructureService service = new InfrastructureService();

        Region west = new Region("india-west", Residency.INDIA);
        Region south = new Region("india-south", Residency.INDIA);
        Region singapore = new Region("singapore", Residency.APAC);

        service.registerRegion(west);
        service.registerRegion(south);
        service.registerRegion(singapore);

        service.registerZone(new Zone("west-a", "india-west", 8, 10));
        service.registerZone(new Zone("west-b", "india-west", 8, 13));
        service.registerZone(new Zone("west-c", "india-west", 8, 16));
        service.registerZone(new Zone("south-a", "india-south", 10, 22));
        service.registerZone(new Zone("south-b", "india-south", 10, 25));
        service.registerZone(new Zone("south-c", "india-south", 10, 27));
        service.registerZone(new Zone("sg-a", "singapore", 12, 55));

        Workload payments = new Workload(
                "payment-api", 9, 3, 30, Residency.INDIA
        );

        service.deploy(payments, Set.of("india-west"));
        System.out.println("Initial placement: " + payments.placement());
        System.out.println("Healthy evaluation: " + service.evaluate(payments));

        service.failZone("west-b");
        System.out.println("After zone failure: " + service.evaluate(payments));

        service.recoverZone("west-b");
        service.failRegion("india-west");
        System.out.println("After regional failure: " + service.evaluate(payments));
        service.recoverRegion("india-west");

        RecoveryObjective objective = new RecoveryObjective(15, 5);
        RecoveryMeasurement measurement = new RecoveryMeasurement(3, 8, 2, true);
        System.out.println("Recovery findings: " + measurement.evaluate(objective));

        try {
            Workload restricted = new Workload(
                    "restricted-ledger", 4, 2, 30, Residency.INDIA
            );
            service.deploy(restricted, Set.of("singapore"));
        } catch (IllegalStateException exception) {
            System.out.println("Placement rejected: " + exception.getMessage());
        }

        service.printInventory();
    }
}
