import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

public class CloudScalingArchitecture {

    enum InstanceState {
        STARTING,
        HEALTHY,
        UNHEALTHY,
        DRAINING,
        TERMINATED
    }

    enum ScalingAction {
        SCALE_OUT,
        SCALE_IN,
        HOLD
    }

    record ScalingPolicy(
        double scaleOutThreshold,
        double scaleInThreshold,
        int minInstances,
        int maxInstances,
        int cooldownTicks) {

        ScalingPolicy {
            if (scaleOutThreshold <= 0
                    || scaleOutThreshold > 1
                    || scaleInThreshold <= 0
                    || scaleInThreshold >= scaleOutThreshold) {
                throw new IllegalArgumentException(
                    "Invalid scaling thresholds");
            }

            if (minInstances < 1
                    || maxInstances < minInstances) {
                throw new IllegalArgumentException(
                    "Invalid instance limits");
            }

            if (cooldownTicks < 0) {
                throw new IllegalArgumentException(
                    "Cooldown cannot be negative");
            }
        }
    }

    static final class Instance {
        private final String id;
        private final int capacityRps;
        private InstanceState state;
        private int activeRequests;

        Instance(String id, int capacityRps) {
            if (id == null || id.isBlank()) {
                throw new IllegalArgumentException(
                    "Instance ID is required");
            }

            if (capacityRps <= 0) {
                throw new IllegalArgumentException(
                    "Capacity must be positive");
            }

            this.id = id;
            this.capacityRps = capacityRps;
            this.state = InstanceState.STARTING;
        }

        String id() {
            return id;
        }

        int capacityRps() {
            return capacityRps;
        }

        InstanceState state() {
            return state;
        }

        void setState(InstanceState state) {
            this.state = Objects.requireNonNull(state);
        }

        void resetLoad() {
            activeRequests = 0;
        }

        int availableCapacity() {
            if (state != InstanceState.HEALTHY) {
                return 0;
            }

            return Math.max(
                0,
                capacityRps - activeRequests);
        }

        void assign(int requests) {
            if (requests < 0
                    || requests > availableCapacity()) {
                throw new IllegalArgumentException(
                    "Invalid request assignment");
            }

            activeRequests += requests;
        }
    }

    record RoutingResult(
        Map<String, Integer> allocation,
        int served,
        int rejected) {
    }

    record ScalingDecision(
        ScalingAction action,
        int instances,
        int healthyInstances,
        int capacityRps,
        RoutingResult routing) {
    }

    static final class AutoScalingService {
        private final ScalingPolicy policy;
        private int cooldownRemaining;

        AutoScalingService(ScalingPolicy policy) {
            this.policy = policy;
        }

        ScalingAction evaluate(
                int requests,
                int capacity) {

            if (capacity <= 0) {
                return ScalingAction.SCALE_OUT;
            }

            if (cooldownRemaining > 0) {
                cooldownRemaining--;
                return ScalingAction.HOLD;
            }

            double utilization =
                (double) requests / capacity;

            if (utilization > policy.scaleOutThreshold()) {
                return ScalingAction.SCALE_OUT;
            }

            if (utilization < policy.scaleInThreshold()) {
                return ScalingAction.SCALE_IN;
            }

            return ScalingAction.HOLD;
        }

        void beginCooldown() {
            cooldownRemaining = policy.cooldownTicks();
        }
    }

    static final class RequestRouter {
        private int cursor;

        RoutingResult route(
                int requestRate,
                List<Instance> instances) {

            if (requestRate < 0) {
                throw new IllegalArgumentException(
                    "Request rate cannot be negative");
            }

            List<Instance> healthy =
                instances.stream()
                    .filter(i ->
                        i.state() == InstanceState.HEALTHY)
                    .toList();

            if (healthy.isEmpty()) {
                return new RoutingResult(
                    Map.of(),
                    0,
                    requestRate);
            }

            Map<String, Integer> allocation =
                new LinkedHashMap<>();

            instances.forEach(
                i -> allocation.put(i.id(), 0));

            int remaining = requestRate;
            int start = cursor % healthy.size();

            while (remaining > 0) {
                boolean progress = false;

                for (int offset = 0;
                     offset < healthy.size();
                     offset++) {

                    Instance instance =
                        healthy.get(
                            (start + offset) % healthy.size());

                    int available =
                        instance.availableCapacity();

                    if (available <= 0) {
                        continue;
                    }

                    int assigned =
                        Math.min(available, remaining);

                    instance.assign(assigned);
                    allocation.merge(
                        instance.id(),
                        assigned,
                        Integer::sum);

                    remaining -= assigned;
                    progress = true;

                    if (remaining == 0) {
                        break;
                    }
                }

                if (!progress) {
                    break;
                }
            }

            cursor =
                (start + 1) % healthy.size();

            return new RoutingResult(
                Collections.unmodifiableMap(allocation),
                requestRate - remaining,
                remaining);
        }
    }

    static final class RepositoryStylePolicy {
        /*
         * This policy object illustrates a useful architectural rule:
         * scaling decisions belong to a dedicated service rather than
         * being embedded inside request-routing code.
         */
        boolean canScaleIn(
                int currentInstances,
                ScalingPolicy policy) {

            return currentInstances > policy.minInstances();
        }

        boolean canScaleOut(
                int currentInstances,
                ScalingPolicy policy) {

            return currentInstances < policy.maxInstances();
        }
    }

    static final class ComputeService {
        private final ScalingPolicy policy;
        private final AutoScalingService autoscaler;
        private final RequestRouter router;
        private final RepositoryStylePolicy governancePolicy;
        private final List<Instance> instances =
            new ArrayList<>();

        private int nextInstanceId = 1;

        ComputeService(ScalingPolicy policy) {
            this.policy = policy;
            this.autoscaler =
                new AutoScalingService(policy);
            this.router = new RequestRouter();
            this.governancePolicy =
                new RepositoryStylePolicy();

            scaleTo(policy.minInstances());
            activateStartingInstances();
        }

        private Instance createInstance() {
            int capacity =
                100 + ((nextInstanceId * 23) % 31);

            return new Instance(
                String.format(
                    "compute-%02d",
                    nextInstanceId++),
                capacity);
        }

        private void activateStartingInstances() {
            instances.stream()
                .filter(i ->
                    i.state() == InstanceState.STARTING)
                .forEach(i ->
                    i.setState(InstanceState.HEALTHY));
        }

        private int activeCount() {
            return (int) instances.stream()
                .filter(i ->
                    i.state() != InstanceState.TERMINATED)
                .count();
        }

        private int healthyCount() {
            return (int) instances.stream()
                .filter(i ->
                    i.state() == InstanceState.HEALTHY)
                .count();
        }

        private int capacity() {
            return instances.stream()
                .filter(i ->
                    i.state() == InstanceState.HEALTHY)
                .mapToInt(Instance::capacityRps)
                .sum();
        }

        private void scaleTo(int desired) {
            desired = Math.max(
                policy.minInstances(),
                Math.min(
                    policy.maxInstances(),
                    desired));

            while (activeCount() < desired) {
                if (!governancePolicy.canScaleOut(
                        activeCount(), policy)) {
                    break;
                }

                instances.add(createInstance());
            }

            while (activeCount() > desired) {
                if (!governancePolicy.canScaleIn(
                        activeCount(), policy)) {
                    break;
                }

                Instance candidate =
                    instances.stream()
                        .filter(i ->
                            i.state() ==
                                InstanceState.HEALTHY)
                        .filter(i ->
                            i.availableCapacity() ==
                                i.capacityRps())
                        .findFirst()
                        .orElse(null);

                if (candidate == null) {
                    break;
                }

                candidate.setState(
                    InstanceState.TERMINATED);
            }

            activateStartingInstances();
        }

        void setHealth(
                String instanceId,
                boolean healthy) {

            Instance instance =
                instances.stream()
                    .filter(i ->
                        i.id().equals(instanceId))
                    .filter(i ->
                        i.state() !=
                            InstanceState.TERMINATED)
                    .findFirst()
                    .orElseThrow(() ->
                        new IllegalArgumentException(
                            "Unknown instance: " +
                            instanceId));

            instance.setState(
                healthy
                    ? InstanceState.HEALTHY
                    : InstanceState.UNHEALTHY);
        }

        ScalingDecision process(int requestRate) {
            if (requestRate < 0) {
                throw new IllegalArgumentException(
                    "Request rate cannot be negative");
            }

            instances.forEach(
                Instance::resetLoad);

            ScalingAction action =
                autoscaler.evaluate(
                    requestRate,
                    capacity());

            if (action == ScalingAction.SCALE_OUT) {
                scaleTo(activeCount() + 1);
                autoscaler.beginCooldown();
            } else if (action == ScalingAction.SCALE_IN) {
                scaleTo(activeCount() - 1);
                autoscaler.beginCooldown();
            }

            RoutingResult routing =
                router.route(requestRate, instances);

            instances.forEach(
                Instance::resetLoad);

            return new ScalingDecision(
                action,
                activeCount(),
                healthyCount(),
                capacity(),
                routing);
        }

        List<Instance> instances() {
            return List.copyOf(instances);
        }
    }

    private static void assertConditions(
            ComputeService service) {

        if (service.instances().size() != 2) {
            throw new AssertionError(
                "Minimum instance count failed");
        }

        ScalingDecision normal =
            service.process(20);

        if (normal.routing().served() != 20
                || normal.routing().rejected() != 0) {
            throw new AssertionError(
                "Normal request routing failed");
        }

        service.setHealth(
            "compute-01",
            false);

        ScalingDecision degraded =
            service.process(20);

        if (degraded.healthyInstances() != 1) {
            throw new AssertionError(
                "Health isolation failed");
        }
    }

    public static void main(String[] args) {
        ScalingPolicy policy =
            new ScalingPolicy(
                0.75,
                0.30,
                2,
                6,
                2);

        ComputeService service =
            new ComputeService(policy);

        assertConditions(service);

        int[] traffic = {
            80, 130, 190, 270,
            460, 620, 300, 150, 70
        };

        System.out.println(
            "Cloud Scaling Architecture");
        System.out.println(
            "=".repeat(78));

        for (int tick = 0;
             tick < traffic.length;
             tick++) {

            if (tick == 5) {
                service.instances().stream()
                    .filter(i ->
                        i.state() ==
                            InstanceState.HEALTHY)
                    .findFirst()
                    .ifPresent(i ->
                        service.setHealth(
                            i.id(), false));
            }

            ScalingDecision decision =
                service.process(traffic[tick]);

            System.out.printf(
                "Tick %02d | requests=%3d | action=%-9s | " +
                "instances=%d | healthy=%d | capacity=%3d | " +
                "served=%3d | rejected=%3d%n",
                tick + 1,
                traffic[tick],
                decision.action(),
                decision.instances(),
                decision.healthyInstances(),
                decision.capacityRps(),
                decision.routing().served(),
                decision.routing().rejected());

            if (tick == 6) {
                service.instances().stream()
                    .filter(i ->
                        i.state() ==
                            InstanceState.UNHEALTHY)
                    .forEach(i ->
                        service.setHealth(
                            i.id(), true));
            }
        }

        System.out.println("\nFinal compute pool:");

        service.instances().forEach(instance ->
            System.out.printf(
                "%s | capacity=%d | state=%s%n",
                instance.id(),
                instance.capacityRps(),
                instance.state()));
    }
}
