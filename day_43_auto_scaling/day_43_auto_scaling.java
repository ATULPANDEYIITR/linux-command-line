import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.Deque;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.function.Consumer;

/**
 * Enterprise auto-scaling model for an API service.
 *
 * Compile and run:
 *     javac AutoScalingEnterprise.java
 *     java AutoScalingEnterprise
 *
 * Requires Java 17 or later. The model is a simulation, not a cloud provider
 * client. Provider-specific APIs, credentials, and deployment operations are
 * intentionally kept outside the domain model.
 */
public class AutoScalingEnterprise {

    enum InstanceState {
        PENDING,
        READY,
        UNHEALTHY
    }

    enum ScalingDirection {
        SCALE_OUT,
        SCALE_IN,
        NO_CHANGE
    }

    record MachineType(
        String name,
        int cpuCores,
        double memoryGb,
        double requestsPerCore,
        double hourlyCost
    ) {
        MachineType {
            Objects.requireNonNull(name, "name");
            if (name.isBlank() || cpuCores <= 0 || memoryGb <= 0
                    || requestsPerCore <= 0 || hourlyCost < 0) {
                throw new IllegalArgumentException("Invalid machine type.");
            }
        }

        double capacityRps() {
            return cpuCores * requestsPerCore;
        }
    }

    record ScalingPolicy(
        int minimumInstances,
        int maximumInstances,
        double scaleOutCpu,
        double scaleInCpu,
        double targetCpu,
        int scaleOutStep,
        int scaleInStep,
        int maximumChangePerEvaluation,
        int cooldownSeconds,
        int warmupSeconds,
        int evaluationSamples
    ) {
        ScalingPolicy {
            if (minimumInstances < 1 || maximumInstances < minimumInstances) {
                throw new IllegalArgumentException("Invalid instance bounds.");
            }
            if (!(scaleInCpu >= 0 && scaleInCpu < scaleOutCpu
                    && scaleOutCpu <= 100)) {
                throw new IllegalArgumentException("Invalid CPU thresholds.");
            }
            if (!(targetCpu > 0 && targetCpu < 100)) {
                throw new IllegalArgumentException("Invalid target CPU.");
            }
            if (scaleOutStep < 1 || scaleInStep < 1
                    || maximumChangePerEvaluation < 1
                    || evaluationSamples < 1) {
                throw new IllegalArgumentException("Invalid scaling steps.");
            }
            if (cooldownSeconds < 0 || warmupSeconds < 0) {
                throw new IllegalArgumentException("Invalid timing policy.");
            }
        }
    }

    static final class ComputeInstance {
        private final String id;
        private final MachineType machineType;
        private InstanceState state;
        private int readyAt;
        private boolean healthy;

        ComputeInstance(
            String id,
            MachineType machineType,
            InstanceState state,
            int readyAt
        ) {
            this.id = Objects.requireNonNull(id);
            this.machineType = Objects.requireNonNull(machineType);
            this.state = Objects.requireNonNull(state);
            this.readyAt = readyAt;
            this.healthy = state != InstanceState.UNHEALTHY;
        }

        String id() {
            return id;
        }

        InstanceState state() {
            return state;
        }

        boolean healthy() {
            return healthy;
        }

        double capacityRps() {
            return machineType.capacityRps();
        }

        double hourlyCost() {
            return machineType.hourlyCost();
        }

        void markUnhealthy() {
            healthy = false;
            state = InstanceState.UNHEALTHY;
        }

        void scheduleRecovery(int readyAt) {
            if (healthy) {
                throw new IllegalStateException("Instance is already healthy.");
            }
            healthy = true;
            state = InstanceState.PENDING;
            this.readyAt = readyAt;
        }

        void advance(int now) {
            if (healthy && state == InstanceState.PENDING && readyAt <= now) {
                state = InstanceState.READY;
            }
        }
    }

    record Sample(
        int time,
        double incomingRps,
        double capacityRps,
        double cpuPercent,
        double servedRps,
        double rejectedRps,
        int desiredInstances,
        int readyInstances,
        int pendingInstances,
        double hourlyCost
    ) {}

    record ScalingEvent(
        int time,
        ScalingDirection direction,
        int previousDesired,
        int newDesired,
        String reason
    ) {}

    static final class DomainEventBus {
        private final Map<Class<?>, List<Consumer<Object>>> listeners =
            new HashMap<>();

        @SuppressWarnings("unchecked")
        <T> void subscribe(Class<T> type, Consumer<T> listener) {
            listeners.computeIfAbsent(type, ignored -> new ArrayList<>())
                .add((Consumer<Object>) (Consumer<?>) listener);
        }

        void publish(Object event) {
            for (Consumer<Object> listener :
                    listeners.getOrDefault(event.getClass(), List.of())) {
                listener.accept(event);
            }
        }
    }

    static final class ScalingService {
        private final MachineType machineType;
        private final ScalingPolicy policy;
        private final DomainEventBus events = new DomainEventBus();
        private final List<ComputeInstance> instances = new ArrayList<>();
        private final List<Sample> samples = new ArrayList<>();
        private final List<ScalingEvent> audit = new ArrayList<>();
        private final Deque<Double> cpuWindow = new ArrayDeque<>();

        private int now;
        private int sequence = 1;
        private int lastScalingTime = Integer.MIN_VALUE / 2;

        ScalingService(MachineType machineType, ScalingPolicy policy) {
            this.machineType = Objects.requireNonNull(machineType);
            this.policy = Objects.requireNonNull(policy);

            for (int i = 0; i < policy.minimumInstances(); i++) {
                instances.add(new ComputeInstance(
                    nextId(), machineType, InstanceState.READY, 0
                ));
            }

            events.subscribe(ScalingEvent.class, event ->
                System.out.printf(
                    "[t=%ds] %s: %d -> %d; %s%n",
                    event.time(),
                    event.direction(),
                    event.previousDesired(),
                    event.newDesired(),
                    event.reason()
                )
            );
        }

        private String nextId() {
            return "api-" + String.format("%03d", sequence++);
        }

        int desiredCount() {
            return instances.size();
        }

        long readyCount() {
            return instances.stream()
                .filter(i -> i.healthy() && i.state() == InstanceState.READY)
                .count();
        }

        long pendingCount() {
            return instances.stream()
                .filter(i -> i.healthy() && i.state() == InstanceState.PENDING)
                .count();
        }

        double readyCapacityRps() {
            return instances.stream()
                .filter(i -> i.healthy() && i.state() == InstanceState.READY)
                .mapToDouble(ComputeInstance::capacityRps)
                .sum();
        }

        double hourlyCost() {
            // Pending machines may incur charges before they serve traffic.
            return instances.stream()
                .filter(ComputeInstance::healthy)
                .mapToDouble(ComputeInstance::hourlyCost)
                .sum();
        }

        void advanceTime(int seconds) {
            if (seconds < 0) {
                throw new IllegalArgumentException("Negative time increment.");
            }
            now += seconds;
            instances.forEach(instance -> instance.advance(now));
        }

        Sample collectMetrics(double incomingRps) {
            if (!Double.isFinite(incomingRps) || incomingRps < 0) {
                throw new IllegalArgumentException("Invalid traffic rate.");
            }

            double capacity = readyCapacityRps();
            double served = Math.min(incomingRps, capacity);
            double rejected = Math.max(0, incomingRps - capacity);
            double cpu = capacity > 0
                ? Math.min(100, incomingRps / capacity * 100)
                : 100;

            Sample sample = new Sample(
                now,
                incomingRps,
                capacity,
                round(cpu),
                served,
                rejected,
                desiredCount(),
                (int) readyCount(),
                (int) pendingCount(),
                hourlyCost()
            );

            samples.add(sample);
            cpuWindow.addLast(cpu);
            while (cpuWindow.size() > policy.evaluationSamples()) {
                cpuWindow.removeFirst();
            }

            return sample;
        }

        ScalingDirection evaluatePolicy() {
            if (cpuWindow.size() < policy.evaluationSamples()) {
                return ScalingDirection.NO_CHANGE;
            }
            if (now - lastScalingTime < policy.cooldownSeconds()) {
                return ScalingDirection.NO_CHANGE;
            }

            double averageCpu = cpuWindow.stream()
                .mapToDouble(Double::doubleValue)
                .average()
                .orElse(0);

            if (averageCpu > policy.scaleOutCpu()) {
                scaleOut(
                    policy.scaleOutStep(),
                    "Sustained CPU above scale-out threshold"
                );
                return ScalingDirection.SCALE_OUT;
            }

            if (averageCpu < policy.scaleInCpu()) {
                scaleIn(
                    policy.scaleInStep(),
                    "Sustained CPU below scale-in threshold"
                );
                return ScalingDirection.SCALE_IN;
            }

            return ScalingDirection.NO_CHANGE;
        }

        int scaleOut(int requested, String reason) {
            if (requested < 1) {
                throw new IllegalArgumentException("Scale-out must be positive.");
            }

            int allowed = Math.min(
                requested,
                Math.min(
                    policy.maximumInstances() - desiredCount(),
                    policy.maximumChangePerEvaluation()
                )
            );

            if (allowed <= 0) {
                return 0;
            }

            int previous = desiredCount();
            for (int i = 0; i < allowed; i++) {
                instances.add(new ComputeInstance(
                    nextId(),
                    machineType,
                    InstanceState.PENDING,
                    now + policy.warmupSeconds()
                ));
            }

            lastScalingTime = now;
            publishAudit(ScalingDirection.SCALE_OUT, previous, reason);
            return allowed;
        }

        int scaleIn(int requested, String reason) {
            if (requested < 1) {
                throw new IllegalArgumentException("Scale-in must be positive.");
            }

            int allowed = Math.min(
                requested,
                Math.min(
                    desiredCount() - policy.minimumInstances(),
                    policy.maximumChangePerEvaluation()
                )
            );

            if (allowed <= 0) {
                return 0;
            }

            int previous = desiredCount();
            List<ComputeInstance> removable = instances.stream()
                .filter(ComputeInstance::healthy)
                .sorted(Comparator
                    .comparing((ComputeInstance i) ->
                        i.state() != InstanceState.PENDING)
                    .thenComparing(ComputeInstance::id, Comparator.reverseOrder()))
                .limit(allowed)
                .toList();

            instances.removeAll(removable);
            lastScalingTime = now;
            publishAudit(ScalingDirection.SCALE_IN, previous, reason);
            return removable.size();
        }

        void markInstanceUnhealthy(String id) {
            ComputeInstance instance = findInstance(id)
                .orElseThrow(() ->
                    new IllegalArgumentException("Unknown instance: " + id));
            instance.markUnhealthy();
        }

        void recoverInstance(String id) {
            ComputeInstance instance = findInstance(id)
                .orElseThrow(() ->
                    new IllegalArgumentException("Unknown instance: " + id));
            instance.scheduleRecovery(now + policy.warmupSeconds());
        }

        private Optional<ComputeInstance> findInstance(String id) {
            return instances.stream()
                .filter(instance -> instance.id().equals(id))
                .findFirst();
        }

        private void publishAudit(
            ScalingDirection direction,
            int previous,
            String reason
        ) {
            ScalingEvent event = new ScalingEvent(
                now, direction, previous, desiredCount(), reason
            );
            audit.add(event);
            events.publish(event);
        }

        List<Sample> samples() {
            return List.copyOf(samples);
        }

        List<ScalingEvent> audit() {
            return List.copyOf(audit);
        }

        void printMetrics() {
            System.out.println(
                "\nTIME  TRAFFIC  CAPACITY  CPU%  READY  PENDING  REJECTED  COST/HR"
            );
            for (Sample sample : samples) {
                System.out.printf(
                    "%4d  %7.1f  %8.1f  %4.1f  %5d  %7d  %8.1f  %7.2f%n",
                    sample.time(),
                    sample.incomingRps(),
                    sample.capacityRps(),
                    sample.cpuPercent(),
                    sample.readyInstances(),
                    sample.pendingInstances(),
                    sample.rejectedRps(),
                    sample.hourlyCost()
                );
            }
        }
    }

    static int requiredFleetSize(
        MachineType machine,
        double demandRps,
        double targetUtilization
    ) {
        if (!Double.isFinite(demandRps) || demandRps < 0
                || !(targetUtilization > 0 && targetUtilization < 1)) {
            throw new IllegalArgumentException("Invalid sizing parameters.");
        }

        return (int) Math.ceil(
            demandRps / (machine.capacityRps() * targetUtilization)
        );
    }

    static double round(double value) {
        return Math.round(value * 100.0) / 100.0;
    }

    public static void main(String[] args) {
        MachineType small = new MachineType(
            "general-small", 2, 4.0, 120.0, 0.08
        );
        MachineType large = new MachineType(
            "general-large", 8, 16.0, 120.0, 0.30
        );

        ScalingPolicy policy = new ScalingPolicy(
            2, 10, 75.0, 25.0, 60.0,
            2, 1, 3, 60, 60, 2
        );

        ScalingService service = new ScalingService(small, policy);

        List<Double> traffic = new ArrayList<>();
        traffic.addAll(java.util.Collections.nCopies(4, 80.0));
        traffic.addAll(java.util.Collections.nCopies(5, 350.0));
        traffic.addAll(java.util.Collections.nCopies(6, 900.0));
        traffic.addAll(java.util.Collections.nCopies(5, 1400.0));
        traffic.addAll(java.util.Collections.nCopies(8, 90.0));

        for (double incomingRps : traffic) {
            service.advanceTime(30);
            Sample sample = service.collectMetrics(incomingRps);
            service.evaluatePolicy();

            if (sample.rejectedRps() > 0) {
                System.out.printf(
                    "Capacity alert at t=%ds: %.1f requests/s rejected%n",
                    sample.time(),
                    sample.rejectedRps()
                );
            }
        }

        service.printMetrics();

        System.out.println("\nVertical sizing at 900 requests/s and 60% utilization");
        for (MachineType machine : List.of(small, large)) {
            int count = requiredFleetSize(machine, 900, 0.60);
            System.out.printf(
                "%s: %d instances, estimated hourly cost $%.2f%n",
                machine.name(),
                count,
                count * machine.hourlyCost()
            );
        }

        System.out.println("\nHealth failure handling");
        service.markInstanceUnhealthy("api-001");
        System.out.printf(
            "Ready capacity after failure: %.1f requests/s%n",
            service.readyCapacityRps()
        );

        // The controller must replace unhealthy capacity within configured
        // bounds. A real service would use cloud health checks and alarms.
        service.scaleOut(1, "Replace unhealthy instance");
        service.advanceTime(policy.warmupSeconds());

        System.out.printf(
            "Ready instances after warmup: %d%n",
            service.readyCount()
        );

        System.out.println(
            "Scaling events recorded: " + service.audit().size()
        );
    }
}
