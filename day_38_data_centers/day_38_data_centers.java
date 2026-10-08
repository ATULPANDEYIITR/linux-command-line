import java.util.ArrayList;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/*
 * Enterprise Data Center Physical Infrastructure Model
 *
 * Java 17 implementation emphasizing explicit domain types, immutable
 * configuration records, validation, state transitions and service-oriented
 * evaluation of physical infrastructure.
 */
public class DataCenterInfrastructure {

    enum EquipmentState {
        ONLINE,
        OFFLINE,
        MAINTENANCE
    }

    enum PowerFeed {
        A,
        B
    }

    enum FailureType {
        POWER_FEED,
        COOLING_UNIT
    }

    record ServerSpec(
            String id,
            String name,
            int rackUnits,
            double watts,
            boolean dualPower
    ) {
        ServerSpec {
            Objects.requireNonNull(id, "Server id is required");
            Objects.requireNonNull(name, "Server name is required");

            if (rackUnits <= 0) {
                throw new IllegalArgumentException(
                        "Rack units must be positive"
                );
            }

            if (watts <= 0) {
                throw new IllegalArgumentException(
                        "Power consumption must be positive"
                );
            }
        }

        double heatKw() {
            return watts / 1000.0;
        }
    }

    record PowerPath(
            String name,
            double capacityKw
    ) {
        PowerPath {
            Objects.requireNonNull(name, "Power path name is required");

            if (capacityKw <= 0) {
                throw new IllegalArgumentException(
                        "Power capacity must be positive"
                );
            }
        }
    }

    static final class InstalledServer {
        private final ServerSpec specification;
        private EquipmentState state;

        InstalledServer(ServerSpec specification) {
            this.specification = specification;
            this.state = EquipmentState.ONLINE;
        }

        ServerSpec specification() {
            return specification;
        }

        EquipmentState state() {
            return state;
        }

        void changeState(EquipmentState newState) {
            if (state == EquipmentState.OFFLINE
                    && newState == EquipmentState.MAINTENANCE) {
                throw new IllegalStateException(
                        "Offline equipment must be restored before maintenance state."
                );
            }

            state = Objects.requireNonNull(newState);
        }

        boolean isOnline() {
            return state == EquipmentState.ONLINE;
        }
    }

    static final class Rack {
        private final String id;
        private final int totalRackUnits;
        private final PowerPath feedA;
        private final PowerPath feedB;
        private final List<InstalledServer> equipment = new ArrayList<>();

        private double feedALoadKw;
        private double feedBLoadKw;
        private boolean feedAOnline = true;
        private boolean feedBOnline = true;

        Rack(String id, int totalRackUnits, double feedCapacityKw) {
            this.id = Objects.requireNonNull(id);
            this.totalRackUnits = totalRackUnits;
            this.feedA = new PowerPath(id + "-A", feedCapacityKw);
            this.feedB = new PowerPath(id + "-B", feedCapacityKw);

            if (totalRackUnits <= 0) {
                throw new IllegalArgumentException(
                        "Rack capacity must be positive"
                );
            }
        }

        String id() {
            return id;
        }

        int usedRackUnits() {
            return equipment.stream()
                    .filter(InstalledServer::isOnline)
                    .mapToInt(item -> item.specification().rackUnits())
                    .sum();
        }

        int freeRackUnits() {
            return totalRackUnits - usedRackUnits();
        }

        double itLoadKw() {
            return equipment.stream()
                    .filter(InstalledServer::isOnline)
                    .mapToDouble(item -> item.specification().heatKw())
                    .sum();
        }

        void install(ServerSpec server) {
            if (server.rackUnits() > freeRackUnits()) {
                throw new IllegalStateException(
                        "Rack " + id + " does not have sufficient rack-unit capacity"
                );
            }

            double loadKw = server.watts() / 1000.0;

            if (server.dualPower()) {
                double halfLoad = loadKw / 2.0;

                if (!feedAOnline || !feedBOnline) {
                    throw new IllegalStateException(
                            "Dual-powered equipment requires both feeds during installation"
                    );
                }

                if (feedALoadKw + halfLoad > feedA.capacityKw()
                        || feedBLoadKw + halfLoad > feedB.capacityKw()) {
                    throw new IllegalStateException(
                            "Rack power capacity would be exceeded"
                    );
                }

                feedALoadKw += halfLoad;
                feedBLoadKw += halfLoad;
            } else {
                if (feedALoadKw + loadKw > feedA.capacityKw()) {
                    throw new IllegalStateException(
                            "Feed A capacity would be exceeded"
                    );
                }

                feedALoadKw += loadKw;
            }

            equipment.add(new InstalledServer(server));
        }

        List<String> failFeed(PowerFeed feed) {
            if (feed == PowerFeed.A) {
                feedAOnline = false;
            } else {
                feedBOnline = false;
            }

            List<String> affected = new ArrayList<>();

            for (InstalledServer server : equipment) {
                if (!server.isOnline()) {
                    continue;
                }

                /*
                 * Dual-corded equipment has an independent second path.
                 * Single-corded equipment in this model is attached to A.
                 */
                if (!server.specification().dualPower()
                        && feed == PowerFeed.A) {
                    server.changeState(EquipmentState.OFFLINE);
                    affected.add(server.specification().id());
                }
            }

            return affected;
        }

        void restoreFeed(PowerFeed feed) {
            if (feed == PowerFeed.A) {
                feedAOnline = true;
            } else {
                feedBOnline = true;
            }

            for (InstalledServer server : equipment) {
                if (server.state() == EquipmentState.OFFLINE) {
                    server.changeState(EquipmentState.ONLINE);
                }
            }
        }

        String report() {
            StringBuilder result = new StringBuilder();

            result.append("Rack ")
                    .append(id)
                    .append(": ")
                    .append(usedRackUnits())
                    .append("/")
                    .append(totalRackUnits)
                    .append("U, A=")
                    .append(String.format("%.2f", feedALoadKw))
                    .append(" kW, B=")
                    .append(String.format("%.2f", feedBLoadKw))
                    .append(" kW\n");

            for (InstalledServer server : equipment) {
                result.append("  ")
                        .append(server.specification().id())
                        .append(" | ")
                        .append(server.specification().name())
                        .append(" | ")
                        .append(server.specification().watts())
                        .append(" W | ")
                        .append(server.state())
                        .append(" | dual=")
                        .append(server.specification().dualPower())
                        .append('\n');
            }

            return result.toString();
        }
    }

    record CoolingUnit(
            String id,
            double capacityKw
    ) {
        CoolingUnit {
            Objects.requireNonNull(id);

            if (capacityKw <= 0) {
                throw new IllegalArgumentException(
                        "Cooling capacity must be positive"
                );
            }
        }
    }

    static final class DataCenter {
        private final String name;
        private final Map<String, Rack> racks = new HashMap<>();
        private final Map<String, CoolingUnit> coolingUnits = new HashMap<>();
        private final Map<String, Boolean> coolingAvailability = new HashMap<>();

        private double ambientTemperatureC = 22.0;
        private double maximumTemperatureC = 27.0;

        DataCenter(String name) {
            this.name = Objects.requireNonNull(name);
        }

        void addRack(Rack rack) {
            if (racks.putIfAbsent(rack.id(), rack) != null) {
                throw new IllegalArgumentException(
                        "Duplicate rack " + rack.id()
                );
            }
        }

        void addCoolingUnit(CoolingUnit unit) {
            if (coolingUnits.putIfAbsent(unit.id(), unit) != null) {
                throw new IllegalArgumentException(
                        "Duplicate cooling unit " + unit.id()
                );
            }

            coolingAvailability.put(unit.id(), true);
        }

        Rack rack(String id) {
            Rack rack = racks.get(id);

            if (rack == null) {
                throw new IllegalArgumentException(
                        "Unknown rack " + id
                );
            }

            return rack;
        }

        double totalItLoadKw() {
            return racks.values()
                    .stream()
                    .mapToDouble(Rack::itLoadKw)
                    .sum();
        }

        double coolingCapacityKw() {
            return coolingUnits.values()
                    .stream()
                    .filter(unit -> Boolean.TRUE.equals(
                            coolingAvailability.get(unit.id())
                    ))
                    .mapToDouble(CoolingUnit::capacityKw)
                    .sum();
        }

        boolean coolingSufficient() {
            return coolingCapacityKw() >= totalItLoadKw();
        }

        boolean nPlusOneCooling() {
            List<Double> capacities = coolingUnits.values()
                    .stream()
                    .filter(unit -> Boolean.TRUE.equals(
                            coolingAvailability.get(unit.id())
                    ))
                    .map(CoolingUnit::capacityKw)
                    .toList();

            if (capacities.size() < 2) {
                return false;
            }

            double total = capacities.stream()
                    .mapToDouble(Double::doubleValue)
                    .sum();

            double largest = capacities.stream()
                    .mapToDouble(Double::doubleValue)
                    .max()
                    .orElse(0);

            return total - largest >= totalItLoadKw();
        }

        void fail(FailureType type, String componentId) {
            switch (type) {
                case POWER_FEED -> {
                    PowerFeed feed = PowerFeed.valueOf(componentId);

                    for (Rack rack : racks.values()) {
                        List<String> affected = rack.failFeed(feed);

                        if (!affected.isEmpty()) {
                            System.out.println(
                                    "Power feed " + feed
                                            + " affected rack " + rack.id()
                                            + ": " + affected
                            );
                        }
                    }
                }
                case COOLING_UNIT -> {
                    if (!coolingAvailability.containsKey(componentId)) {
                        throw new IllegalArgumentException(
                                "Unknown cooling unit " + componentId
                        );
                    }

                    coolingAvailability.put(componentId, false);
                }
            }
        }

        void restoreCooling(String id) {
            if (!coolingAvailability.containsKey(id)) {
                throw new IllegalArgumentException(
                        "Unknown cooling unit " + id
                );
            }

            coolingAvailability.put(id, true);
        }

        void setAmbientTemperature(double temperatureC) {
            if (temperatureC < -50 || temperatureC > 80) {
                throw new IllegalArgumentException(
                        "Temperature outside supported simulation range"
                );
            }

            ambientTemperatureC = temperatureC;
        }

        boolean temperatureSafe() {
            return ambientTemperatureC <= maximumTemperatureC;
        }

        void printReport() {
            System.out.println("\n=== " + name + " ===");
            System.out.printf(
                    "IT load: %.2f kW%n",
                    totalItLoadKw()
            );
            System.out.printf(
                    "Cooling capacity: %.2f kW%n",
                    coolingCapacityKw()
            );
            System.out.println(
                    "Cooling sufficient: " + coolingSufficient()
            );
            System.out.println(
                    "Cooling N+1: " + nPlusOneCooling()
            );
            System.out.printf(
                    "Temperature: %.1f°C, safe=%s%n",
                    ambientTemperatureC,
                    temperatureSafe()
            );

            racks.values()
                    .stream()
                    .sorted((a, b) -> a.id().compareTo(b.id()))
                    .forEach(rack -> System.out.print(rack.report()));
        }
    }

    static final class InfrastructureEvaluationService {

        record Evaluation(
                boolean coolingAvailable,
                boolean coolingNPlusOne,
                boolean temperatureSafe,
                double itLoadKw,
                double coolingCapacityKw
        ) {
            boolean healthy() {
                return coolingAvailable
                        && coolingNPlusOne
                        && temperatureSafe;
            }
        }

        Evaluation evaluate(DataCenter dataCenter) {
            return new Evaluation(
                    dataCenter.coolingSufficient(),
                    dataCenter.nPlusOneCooling(),
                    dataCenter.temperatureSafe(),
                    dataCenter.totalItLoadKw(),
                    dataCenter.coolingCapacityKw()
            );
        }

        void printEvaluation(Evaluation evaluation) {
            System.out.println("\nINFRASTRUCTURE EVALUATION");
            System.out.println(
                    "Cooling available: " + evaluation.coolingAvailable()
            );
            System.out.println(
                    "Cooling N+1: " + evaluation.coolingNPlusOne()
            );
            System.out.println(
                    "Temperature safe: " + evaluation.temperatureSafe()
            );
            System.out.printf(
                    "IT load: %.2f kW%n",
                    evaluation.itLoadKw()
            );
            System.out.printf(
                    "Cooling capacity: %.2f kW%n",
                    evaluation.coolingCapacityKw()
            );
            System.out.println(
                    "Facility state: "
                            + (evaluation.healthy() ? "HEALTHY" : "ATTENTION REQUIRED")
            );
        }
    }

    public static void main(String[] args) {
        DataCenter facility =
                new DataCenter("Enterprise Regional Data Center");

        facility.addRack(new Rack("R01", 42, 10));
        facility.addRack(new Rack("R02", 42, 10));
        facility.addRack(new Rack("R03", 42, 10));

        facility.addCoolingUnit(new CoolingUnit("CRAC-01", 8));
        facility.addCoolingUnit(new CoolingUnit("CRAC-02", 8));
        facility.addCoolingUnit(new CoolingUnit("CRAC-03", 8));

        facility.rack("R01").install(
                new ServerSpec(
                        "SRV-001",
                        "Virtualization Host",
                        2,
                        900,
                        true
                )
        );

        facility.rack("R01").install(
                new ServerSpec(
                        "SRV-002",
                        "Database Host",
                        2,
                        750,
                        true
                )
        );

        facility.rack("R01").install(
                new ServerSpec(
                        "SRV-003",
                        "Facilities Gateway",
                        1,
                        250,
                        false
                )
        );

        facility.rack("R02").install(
                new ServerSpec(
                        "SRV-004",
                        "Storage Controller",
                        2,
                        700,
                        true
                )
        );

        facility.rack("R03").install(
                new ServerSpec(
                        "SRV-005",
                        "High Density Compute",
                        4,
                        1400,
                        true
                )
        );

        InfrastructureEvaluationService evaluator =
                new InfrastructureEvaluationService();

        facility.printReport();
        evaluator.printEvaluation(evaluator.evaluate(facility));

        System.out.println("\n=== POWER FEED FAILURE ===");
        facility.fail(FailureType.POWER_FEED, "A");
        facility.printReport();
        evaluator.printEvaluation(evaluator.evaluate(facility));

        System.out.println("\n=== COOLING UNIT FAILURE ===");
        facility.fail(FailureType.COOLING_UNIT, "CRAC-01");
        evaluator.printEvaluation(evaluator.evaluate(facility));

        System.out.println("\n=== TEMPERATURE EXCURSION ===");
        facility.setAmbientTemperature(30);
        evaluator.printEvaluation(evaluator.evaluate(facility));

        System.out.println("\n=== RECOVERY ===");
        facility.restoreCooling("CRAC-01");
        facility.setAmbientTemperature(22);
        facility.rack("R01").restoreFeed(PowerFeed.A);

        facility.printReport();
        evaluator.printEvaluation(evaluator.evaluate(facility));
    }
}
