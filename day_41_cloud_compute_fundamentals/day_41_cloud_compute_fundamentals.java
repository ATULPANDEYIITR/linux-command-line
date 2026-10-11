import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

public class CloudComputeEnterprise {

    enum InstanceFamily {
        GENERAL_PURPOSE,
        COMPUTE_OPTIMIZED,
        MEMORY_OPTIMIZED,
        BURSTABLE,
        ACCELERATED
    }

    enum InstanceState {
        REQUESTED,
        PROVISIONING,
        RUNNING,
        STOPPED,
        TERMINATED,
        FAILED
    }

    record InstanceType(
            String name,
            InstanceFamily family,
            int vcpus,
            double memoryGiB,
            BigDecimal hourlyRate,
            String architecture,
            double networkGbps) {

        InstanceType {
            Objects.requireNonNull(name);
            Objects.requireNonNull(family);
            Objects.requireNonNull(hourlyRate);
            Objects.requireNonNull(architecture);

            if (name.isBlank() || vcpus <= 0 || memoryGiB <= 0
                    || hourlyRate.signum() < 0 || networkGbps <= 0) {
                throw new IllegalArgumentException(
                        "Invalid compute instance specification");
            }
        }

        double memoryPerVcpu() {
            return memoryGiB / vcpus;
        }
    }

    record ComputePolicy(
            int minimumVcpus,
            double minimumMemoryGiB,
            BigDecimal maximumHourlyRate,
            Set<InstanceFamily> permittedFamilies,
            Set<String> permittedArchitectures) {

        ComputePolicy {
            Objects.requireNonNull(maximumHourlyRate);
            permittedFamilies = Set.copyOf(permittedFamilies);
            permittedArchitectures = Set.copyOf(permittedArchitectures);

            if (minimumVcpus <= 0 || minimumMemoryGiB <= 0
                    || maximumHourlyRate.signum() < 0
                    || permittedFamilies.isEmpty()
                    || permittedArchitectures.isEmpty()) {
                throw new IllegalArgumentException("Invalid compute policy");
            }
        }

        boolean permits(InstanceType type) {
            return type.vcpus() >= minimumVcpus
                    && type.memoryGiB() >= minimumMemoryGiB
                    && type.hourlyRate().compareTo(maximumHourlyRate) <= 0
                    && permittedFamilies.contains(type.family())
                    && permittedArchitectures.contains(type.architecture());
        }
    }

    static final class PhysicalHost {
        private final String id;
        private final int totalVcpus;
        private final double totalMemoryGiB;
        private final Set<String> architectures;
        private final Map<String, InstanceType> reservations = new HashMap<>();

        PhysicalHost(
                String id,
                int totalVcpus,
                double totalMemoryGiB,
                Set<String> architectures) {
            if (id == null || id.isBlank()
                    || totalVcpus <= 0 || totalMemoryGiB <= 0) {
                throw new IllegalArgumentException("Invalid host definition");
            }
            this.id = id;
            this.totalVcpus = totalVcpus;
            this.totalMemoryGiB = totalMemoryGiB;
            this.architectures = Set.copyOf(architectures);
        }

        int usedVcpus() {
            return reservations.values().stream()
                    .mapToInt(InstanceType::vcpus).sum();
        }

        double usedMemoryGiB() {
            return reservations.values().stream()
                    .mapToDouble(InstanceType::memoryGiB).sum();
        }

        boolean canFit(InstanceType type) {
            return architectures.contains(type.architecture())
                    && totalVcpus - usedVcpus() >= type.vcpus()
                    && totalMemoryGiB - usedMemoryGiB() >= type.memoryGiB();
        }

        void reserve(String instanceId, InstanceType type) {
            if (reservations.containsKey(instanceId)) {
                throw new IllegalStateException("Duplicate reservation");
            }
            if (!canFit(type)) {
                throw new IllegalStateException("Insufficient host capacity");
            }
            reservations.put(instanceId, type);
        }

        void release(String instanceId) {
            if (reservations.remove(instanceId) == null) {
                throw new IllegalStateException("Missing resource reservation");
            }
        }

        String id() {
            return id;
        }

        int freeVcpus() {
            return totalVcpus - usedVcpus();
        }

        double freeMemoryGiB() {
            return totalMemoryGiB - usedMemoryGiB();
        }
    }

    static final class ComputeInstance {
        private final String id;
        private final String workload;
        private final InstanceType type;
        private final Map<String, String> tags;
        private InstanceState state = InstanceState.REQUESTED;
        private String hostId;

        private static final Map<InstanceState, Set<InstanceState>> TRANSITIONS;

        static {
            Map<InstanceState, Set<InstanceState>> transitions =
                    new EnumMap<>(InstanceState.class);
            transitions.put(InstanceState.REQUESTED,
                    Set.of(InstanceState.PROVISIONING, InstanceState.FAILED));
            transitions.put(InstanceState.PROVISIONING,
                    Set.of(InstanceState.RUNNING, InstanceState.FAILED,
                            InstanceState.STOPPED));
            transitions.put(InstanceState.RUNNING,
                    Set.of(InstanceState.STOPPED, InstanceState.TERMINATED));
            transitions.put(InstanceState.STOPPED,
                    Set.of(InstanceState.PROVISIONING, InstanceState.TERMINATED));
            transitions.put(InstanceState.FAILED,
                    Set.of(InstanceState.TERMINATED));
            transitions.put(InstanceState.TERMINATED, Set.of());
            TRANSITIONS = Map.copyOf(transitions);
        }

        ComputeInstance(
                String id,
                String workload,
                InstanceType type,
                Map<String, String> tags) {
            this.id = id;
            this.workload = workload;
            this.type = type;
            this.tags = Map.copyOf(tags);
        }

        void transition(InstanceState target) {
            if (!TRANSITIONS.get(state).contains(target)) {
                throw new IllegalStateException(
                        "Illegal transition: " + state + " -> " + target);
            }
            state = target;
        }

        String id() {
            return id;
        }

        String workload() {
            return workload;
        }

        InstanceType type() {
            return type;
        }

        InstanceState state() {
            return state;
        }

        String hostId() {
            return hostId;
        }

        Map<String, String> tags() {
            return tags;
        }
    }

    static final class ComputeService {
        private final Map<String, InstanceType> catalog = new HashMap<>();
        private final Map<String, PhysicalHost> hosts = new HashMap<>();
        private final Map<String, ComputeInstance> instances = new HashMap<>();
        private int nextId = 1;

        void registerType(InstanceType type) {
            if (catalog.putIfAbsent(type.name(), type) != null) {
                throw new IllegalArgumentException("Duplicate instance type");
            }
        }

        void registerHost(PhysicalHost host) {
            if (hosts.putIfAbsent(host.id(), host) != null) {
                throw new IllegalArgumentException("Duplicate physical host");
            }
        }

        InstanceType select(ComputePolicy policy) {
            return catalog.values().stream()
                    .filter(policy::permits)
                    .min(Comparator
                            .comparing(InstanceType::hourlyRate)
                            .thenComparingInt(InstanceType::vcpus)
                            .thenComparingDouble(InstanceType::memoryGiB))
                    .orElseThrow(() -> new IllegalStateException(
                            "No instance type satisfies the policy"));
        }

        ComputeInstance provision(
                String typeName,
                String workload,
                Map<String, String> tags) {
            if (workload == null || workload.isBlank()) {
                throw new IllegalArgumentException("Workload is required");
            }

            InstanceType type = catalog.get(typeName);
            if (type == null) {
                throw new IllegalArgumentException(
                        "Unknown instance type: " + typeName);
            }

            String id = "vm-" + String.format("%04d", nextId++);
            ComputeInstance instance =
                    new ComputeInstance(id, workload, type, tags);
            instances.put(id, instance);
            instance.transition(InstanceState.PROVISIONING);

            List<PhysicalHost> candidates = new ArrayList<>(hosts.values());
            candidates.sort(Comparator
                    .comparingDouble(PhysicalHost::freeMemoryGiB).reversed()
                    .thenComparingInt(PhysicalHost::freeVcpus).reversed()
                    .thenComparing(PhysicalHost::id));

            for (PhysicalHost host : candidates) {
                if (!host.canFit(type)) {
                    continue;
                }
                host.reserve(id, type);
                instance.hostId = host.id();
                instance.transition(InstanceState.RUNNING);
                return instance;
            }

            instance.transition(InstanceState.FAILED);
            throw new IllegalStateException(
                    "No compatible physical host has sufficient capacity");
        }

        void stop(String id) {
            ComputeInstance instance = get(id);
            instance.transition(InstanceState.STOPPED);
            releaseHost(instance);
        }

        void start(String id) {
            ComputeInstance instance = get(id);
            instance.transition(InstanceState.PROVISIONING);

            for (PhysicalHost host : hosts.values()) {
                if (!host.canFit(instance.type())) {
                    continue;
                }
                host.reserve(id, instance.type());
                instance.hostId = host.id();
                instance.transition(InstanceState.RUNNING);
                return;
            }

            instance.transition(InstanceState.STOPPED);
            throw new IllegalStateException("Insufficient capacity to restart");
        }

        void terminate(String id) {
            ComputeInstance instance = get(id);
            releaseHost(instance);
            instance.transition(InstanceState.TERMINATED);
        }

        private void releaseHost(ComputeInstance instance) {
            if (instance.hostId == null) {
                return;
            }
            PhysicalHost host = hosts.get(instance.hostId);
            if (host == null) {
                throw new IllegalStateException("Assigned host does not exist");
            }
            host.release(instance.id());
            instance.hostId = null;
        }

        private ComputeInstance get(String id) {
            ComputeInstance instance = instances.get(id);
            if (instance == null) {
                throw new IllegalArgumentException("Unknown instance: " + id);
            }
            return instance;
        }

        void report() {
            System.out.println("\nInstance inventory");
            for (ComputeInstance instance : instances.values()) {
                System.out.printf(
                        "%s | %-20s | %-15s | %2d vCPU | %5.1f GiB | %s | %s%n",
                        instance.id(),
                        instance.workload(),
                        instance.type().name(),
                        instance.type().vcpus(),
                        instance.type().memoryGiB(),
                        instance.state(),
                        instance.hostId() == null ? "-" : instance.hostId());
            }

            System.out.println("\nPhysical host headroom");
            for (PhysicalHost host : hosts.values()) {
                System.out.printf(
                        "%s: %d vCPUs and %.1f GiB RAM free%n",
                        host.id(), host.freeVcpus(), host.freeMemoryGiB());
            }
        }
    }

    static BigDecimal computeCost(
            BigDecimal hourlyRate,
            BigDecimal hours,
            int instanceCount) {
        if (hourlyRate.signum() < 0 || hours.signum() < 0
                || instanceCount <= 0) {
            throw new IllegalArgumentException("Invalid cost inputs");
        }
        return hourlyRate.multiply(hours)
                .multiply(BigDecimal.valueOf(instanceCount))
                .setScale(2, RoundingMode.HALF_UP);
    }

    public static void main(String[] args) {
        ComputeService service = new ComputeService();

        service.registerType(new InstanceType(
                "general-medium", InstanceFamily.GENERAL_PURPOSE,
                4, 16, new BigDecimal("0.16"), "x86_64", 10));
        service.registerType(new InstanceType(
                "cpu-large", InstanceFamily.COMPUTE_OPTIMIZED,
                8, 16, new BigDecimal("0.24"), "x86_64", 15));
        service.registerType(new InstanceType(
                "memory-large", InstanceFamily.MEMORY_OPTIMIZED,
                4, 32, new BigDecimal("0.22"), "x86_64", 10));
        service.registerType(new InstanceType(
                "arm-burst", InstanceFamily.BURSTABLE,
                2, 4, new BigDecimal("0.035"), "arm64", 2));

        service.registerHost(new PhysicalHost(
                "node-a", 16, 64, Set.of("x86_64", "arm64")));
        service.registerHost(new PhysicalHost(
                "node-b", 8, 32, Set.of("x86_64")));

        ComputePolicy databasePolicy = new ComputePolicy(
                4, 24, new BigDecimal("0.30"),
                Set.of(InstanceFamily.MEMORY_OPTIMIZED),
                Set.of("x86_64"));

        InstanceType selected = service.select(databasePolicy);
        System.out.println("Database sizing decision: " + selected.name());
        System.out.println("Memory per vCPU: " + selected.memoryPerVcpu());

        ComputeInstance database = service.provision(
                selected.name(),
                "orders-database",
                Map.of("environment", "production", "owner", "data-platform"));

        ComputeInstance api = service.provision(
                "general-medium",
                "orders-api",
                Map.of("environment", "production"));

        service.report();

        System.out.println("\nThree general-medium instances for eight hours: $"
                + computeCost(
                        new BigDecimal("0.16"),
                        new BigDecimal("8"),
                        3));

        service.stop(api.id());
        service.start(api.id());
        service.terminate(api.id());
        service.terminate(database.id());

        try {
            service.provision(
                    "unknown-type", "invalid-workload", Map.of());
        } catch (IllegalArgumentException | IllegalStateException exception) {
            System.out.println("Expected provisioning failure: "
                    + exception.getMessage());
        }

        try {
            database.transition(InstanceState.RUNNING);
        } catch (IllegalStateException exception) {
            System.out.println("Expected lifecycle rejection: "
                    + exception.getMessage());
        }

        service.report();
    }
}
