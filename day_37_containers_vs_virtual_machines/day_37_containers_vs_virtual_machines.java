import java.util.ArrayList;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;

/**
 * Containers vs Virtual Machines
 *
 * Enterprise-oriented repository:
 * A platform engineering organization evaluates workload placement using
 * explicit domain rules for isolation, resource consumption, portability,
 * operating-system requirements, and deployment characteristics.
 *
 * Requires Java 17 or later.
 */
public class ContainerVsVm {

    enum DeploymentType {
        CONTAINER,
        VIRTUAL_MACHINE
    }

    enum WorkloadType {
        MICROSERVICE,
        DATABASE,
        LEGACY_APPLICATION,
        BATCH_PROCESS
    }

    enum DeploymentDecision {
        APPROVED,
        REJECTED
    }

    record ResourceRequest(
            double cpuCores,
            double memoryGiB,
            double storageGiB) {

        ResourceRequest {
            if (cpuCores <= 0 || memoryGiB <= 0 || storageGiB <= 0) {
                throw new IllegalArgumentException(
                        "All resource requests must be positive.");
            }
        }
    }

    record Host(
            String name,
            double cpuCores,
            double memoryGiB,
            double storageGiB,
            String kernel) {

        Host {
            if (cpuCores <= 0 || memoryGiB <= 0 || storageGiB <= 0) {
                throw new IllegalArgumentException(
                        "Host resources must be positive.");
            }
        }
    }

    record IsolationPolicy(
            boolean sharesHostKernel,
            boolean hasGuestKernel,
            boolean hasVirtualHardwareBoundary,
            double isolationScore,
            String boundaryDescription) {

        IsolationPolicy {
            if (isolationScore < 0 || isolationScore > 1) {
                throw new IllegalArgumentException(
                        "Isolation score must be between zero and one.");
            }
        }
    }

    record RuntimeProfile(
            DeploymentType type,
            String name,
            IsolationPolicy isolation,
            double memoryOverheadGiB,
            double cpuOverheadPercent,
            double startupSeconds,
            double storageOverheadGiB,
            boolean hostKernelCompatibilityRequired) {

        RuntimeProfile {
            if (memoryOverheadGiB < 0 ||
                    cpuOverheadPercent < 0 ||
                    startupSeconds < 0 ||
                    storageOverheadGiB < 0) {
                throw new IllegalArgumentException(
                        "Runtime overhead values cannot be negative.");
            }
        }

        double estimatedMemory(ResourceRequest request) {
            return request.memoryGiB() + memoryOverheadGiB;
        }

        double estimatedCpu(ResourceRequest request) {
            return request.cpuCores() *
                    (1 + cpuOverheadPercent / 100.0);
        }

        double estimatedStorage(ResourceRequest request) {
            return request.storageGiB() + storageOverheadGiB;
        }
    }

    record Workload(
            String name,
            WorkloadType type,
            ResourceRequest resources,
            boolean requiresStrongIsolation,
            boolean requiresSpecificGuestOs) {

        Workload {
            if (name == null || name.isBlank()) {
                throw new IllegalArgumentException(
                        "Workload name cannot be blank.");
            }
            if (type == null || resources == null) {
                throw new IllegalArgumentException(
                        "Workload type and resources are required.");
            }
        }
    }

    record ResourceEstimate(
            DeploymentType deploymentType,
            int instanceCount,
            double memoryGiB,
            double cpuCores,
            double storageGiB,
            double memoryUtilization,
            double cpuUtilization,
            double storageUtilization) {
    }

    record DeploymentResult(
            DeploymentDecision decision,
            String reason,
            ResourceEstimate estimate) {
    }

    interface PlacementRule {
        boolean accepts(Workload workload, RuntimeProfile profile);

        String reason();
    }

    static final class StrongIsolationRule implements PlacementRule {
        @Override
        public boolean accepts(
                Workload workload,
                RuntimeProfile profile) {

            return !workload.requiresStrongIsolation()
                    || profile.isolation().isolationScore() >= 0.90;
        }

        @Override
        public String reason() {
            return "The workload requires a strong isolation boundary.";
        }
    }

    static final class GuestOperatingSystemRule implements PlacementRule {
        @Override
        public boolean accepts(
                Workload workload,
                RuntimeProfile profile) {

            return !workload.requiresSpecificGuestOs()
                    || profile.type() == DeploymentType.VIRTUAL_MACHINE;
        }

        @Override
        public String reason() {
            return "The workload requires an independent guest operating system.";
        }
    }

    static final class CapacityRule implements PlacementRule {
        private final Host host;

        CapacityRule(Host host) {
            this.host = host;
        }

        @Override
        public boolean accepts(
                Workload workload,
                RuntimeProfile profile) {

            ResourceEstimate estimate = estimate(
                    workload,
                    profile,
                    1);

            return estimate.memoryUtilization() <= 100
                    && estimate.cpuUtilization() <= 100
                    && estimate.storageUtilization() <= 100;
        }

        @Override
        public String reason() {
            return "The workload exceeds available host capacity.";
        }

        private ResourceEstimate estimate(
                Workload workload,
                RuntimeProfile profile,
                int count) {

            double memory =
                    count * profile.estimatedMemory(workload.resources());

            double cpu =
                    count * profile.estimatedCpu(workload.resources());

            double storage =
                    count * profile.estimatedStorage(workload.resources());

            return new ResourceEstimate(
                    profile.type(),
                    count,
                    memory,
                    cpu,
                    storage,
                    memory / host.memoryGiB() * 100,
                    cpu / host.cpuCores() * 100,
                    storage / host.storageGiB() * 100);
        }
    }

    static final class PlacementService {
        private final Host host;
        private final Map<DeploymentType, RuntimeProfile> profiles;
        private final List<PlacementRule> rules;

        PlacementService(
                Host host,
                Map<DeploymentType, RuntimeProfile> profiles,
                List<PlacementRule> rules) {

            this.host = host;
            this.profiles = Map.copyOf(profiles);
            this.rules = List.copyOf(rules);
        }

        DeploymentResult evaluate(
                Workload workload,
                DeploymentType type,
                int instances) {

            if (instances <= 0) {
                throw new IllegalArgumentException(
                        "Instance count must be positive.");
            }

            RuntimeProfile profile = profiles.get(type);

            if (profile == null) {
                throw new IllegalArgumentException(
                        "No runtime profile exists for " + type);
            }

            for (PlacementRule rule : rules) {
                if (!rule.accepts(workload, profile)) {
                    return new DeploymentResult(
                            DeploymentDecision.REJECTED,
                            rule.reason(),
                            estimate(workload, profile, instances));
                }
            }

            return new DeploymentResult(
                    DeploymentDecision.APPROVED,
                    "All placement rules passed.",
                    estimate(workload, profile, instances));
        }

        private ResourceEstimate estimate(
                Workload workload,
                RuntimeProfile profile,
                int instances) {

            double memory =
                    instances * profile.estimatedMemory(workload.resources());

            double cpu =
                    instances * profile.estimatedCpu(workload.resources());

            double storage =
                    instances * profile.estimatedStorage(workload.resources());

            return new ResourceEstimate(
                    profile.type(),
                    instances,
                    memory,
                    cpu,
                    storage,
                    memory / host.memoryGiB() * 100,
                    cpu / host.cpuCores() * 100,
                    storage / host.storageGiB() * 100);
        }
    }

    static final class DeploymentStateMachine {
        enum State {
            CREATED,
            STARTING,
            RUNNING,
            STOPPED,
            FAILED
        }

        private State state = State.CREATED;

        State state() {
            return state;
        }

        void start() {
            if (state != State.CREATED && state != State.STOPPED) {
                throw new IllegalStateException(
                        "A deployment can only start from CREATED or STOPPED.");
            }

            state = State.STARTING;

            // In a production system, this transition would surround actual
            // runtime or hypervisor provisioning and health verification.
            state = State.RUNNING;
        }

        void stop() {
            if (state != State.RUNNING) {
                throw new IllegalStateException(
                        "Only a running deployment can be stopped.");
            }

            state = State.STOPPED;
        }

        void fail() {
            if (state == State.STOPPED) {
                throw new IllegalStateException(
                        "A stopped deployment cannot transition directly to FAILED.");
            }

            state = State.FAILED;
        }
    }

    private static RuntimeProfile containerProfile() {
        return new RuntimeProfile(
                DeploymentType.CONTAINER,
                "Container",
                new IsolationPolicy(
                        true,
                        false,
                        false,
                        0.72,
                        "OS-level isolation with shared host kernel"),
                0.08,
                2.0,
                0.8,
                0.15,
                true);
    }

    private static RuntimeProfile vmProfile() {
        return new RuntimeProfile(
                DeploymentType.VIRTUAL_MACHINE,
                "Virtual Machine",
                new IsolationPolicy(
                        false,
                        true,
                        true,
                        0.96,
                        "hardware-assisted virtualization boundary"),
                0.90,
                7.0,
                25.0,
                8.0,
                false);
    }

    private static void printResult(
            Workload workload,
            DeploymentResult result) {

        ResourceEstimate estimate = result.estimate();

        System.out.printf(
                "%n%s -> %s%n",
                workload.name(),
                estimate.deploymentType());

        System.out.println("Decision: " + result.decision());
        System.out.println("Reason: " + result.reason());

        System.out.printf(
                "Memory: %.2f GiB (%.1f%%)%n",
                estimate.memoryGiB(),
                estimate.memoryUtilization());

        System.out.printf(
                "CPU: %.2f cores (%.1f%%)%n",
                estimate.cpuCores(),
                estimate.cpuUtilization());

        System.out.printf(
                "Storage: %.2f GiB (%.1f%%)%n",
                estimate.storageGiB(),
                estimate.storageUtilization());
    }

    private static void printArchitecture(
            Map<DeploymentType, RuntimeProfile> profiles) {

        System.out.println("=== Architecture ===");

        for (RuntimeProfile profile : profiles.values()) {
            System.out.println("\n" + profile.name());

            System.out.println(
                    "Kernel: " +
                            (profile.isolation().sharesHostKernel()
                                    ? "shared host kernel"
                                    : "independent guest kernel"));

            System.out.println(
                    "Virtual hardware boundary: " +
                            profile.isolation().hasVirtualHardwareBoundary());

            System.out.println(
                    "Isolation score: " +
                            profile.isolation().isolationScore());

            System.out.println(
                    "Boundary: " +
                            profile.isolation().boundaryDescription());
        }
    }

    private static void printPortability(
            Map<DeploymentType, RuntimeProfile> profiles) {

        System.out.println("\n=== Portability ===");

        List<String> hostKernels = List.of(
                "Linux 6.12",
                "Linux 6.8",
                "Windows Server 2025",
                "FreeBSD 14");

        for (RuntimeProfile profile : profiles.values()) {
            long compatible;

            if (profile.type() == DeploymentType.VIRTUAL_MACHINE) {
                compatible = hostKernels.size();
            } else {
                compatible = hostKernels.stream()
                        .filter(kernel -> kernel.startsWith("Linux"))
                        .count();
            }

            double percentage =
                    compatible * 100.0 / hostKernels.size();

            System.out.printf(
                    "%s compatibility model: %.1f%%%n",
                    profile.name(),
                    percentage);
        }

        System.out.println(
                "The VM model carries a guest kernel, while a container "
                        + "requires compatible host kernel facilities.");
    }

    public static void main(String[] args) {
        Host host = new Host(
                "production-node",
                16,
                64,
                500,
                "Linux 6.12");

        Map<DeploymentType, RuntimeProfile> profiles =
                new EnumMap<>(DeploymentType.class);

        profiles.put(
                DeploymentType.CONTAINER,
                containerProfile());

        profiles.put(
                DeploymentType.VIRTUAL_MACHINE,
                vmProfile());

        List<PlacementRule> rules = List.of(
                new StrongIsolationRule(),
                new GuestOperatingSystemRule(),
                new CapacityRule(host));

        PlacementService service =
                new PlacementService(host, profiles, rules);

        printArchitecture(profiles);

        Workload apiService = new Workload(
                "Payment API",
                WorkloadType.MICROSERVICE,
                new ResourceRequest(0.25, 1, 0.2),
                false,
                false);

        Workload legacySystem = new Workload(
                "Legacy ERP connector",
                WorkloadType.LEGACY_APPLICATION,
                new ResourceRequest(1.5, 4, 8),
                true,
                true);

        Workload database = new Workload(
                "Transactional database",
                WorkloadType.DATABASE,
                new ResourceRequest(2, 8, 20),
                true,
                false);

        System.out.println("\n=== Enterprise Placement ===");

        for (DeploymentType type : DeploymentType.values()) {
            printResult(
                    apiService,
                    service.evaluate(apiService, type, 30));
        }

        for (DeploymentType type : DeploymentType.values()) {
            printResult(
                    legacySystem,
                    service.evaluate(legacySystem, type, 5));
        }

        for (DeploymentType type : DeploymentType.values()) {
            printResult(
                    database,
                    service.evaluate(database, type, 4));
        }

        printPortability(profiles);

        System.out.println("\n=== Deployment State Machine ===");

        DeploymentStateMachine stateMachine =
                new DeploymentStateMachine();

        System.out.println("Initial state: " + stateMachine.state());

        stateMachine.start();
        System.out.println("After start: " + stateMachine.state());

        stateMachine.stop();
        System.out.println("After stop: " + stateMachine.state());

        try {
            stateMachine.stop();
        } catch (IllegalStateException error) {
            System.out.println(
                    "Invalid transition rejected: " +
                            error.getMessage());
        }

        System.out.println("\n=== Architectural Interpretation ===");

        System.out.println(
                "Containers are generally preferred for dense, rapidly "
                        + "replaceable application workloads.");

        System.out.println(
                "VMs are generally preferred when guest-kernel independence, "
                        + "heterogeneous operating systems, or stronger "
                        + "tenant isolation is a primary requirement.");
    }
}
