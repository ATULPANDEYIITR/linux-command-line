#include <algorithm>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

/*
 * Enterprise Data Center Physical Infrastructure Governance Case Study
 *
 * Scenario:
 * A facility operations team needs a deterministic engine that evaluates
 * rack capacity, electrical feeds, cooling capacity, redundancy and
 * equipment impact when physical infrastructure fails.
 *
 * The program uses C++17 standard-library facilities only.
 */

enum class EquipmentState {
    Online,
    Offline,
    Maintenance
};

enum class Feed {
    A,
    B
};

struct Server {
    std::string id;
    std::string name;
    int rackUnits;
    double watts;
    bool dualPower;
    EquipmentState state{EquipmentState::Online};

    double heatKw() const {
        return watts / 1000.0;
    }
};

struct PowerPath {
    std::string name;
    double capacityKw;
    double loadKw{0.0};
    bool online{true};

    bool canAccept(double additionalKw) const {
        return online && loadKw + additionalKw <= capacityKw + 1e-9;
    }

    void addLoad(double additionalKw) {
        if (!canAccept(additionalKw)) {
            throw std::runtime_error(
                "Power path " + name + " cannot accept requested load."
            );
        }
        loadKw += additionalKw;
    }

    void removeLoad(double amountKw) {
        loadKw = std::max(0.0, loadKw - amountKw);
    }
};

class Rack {
private:
    std::string id_;
    int totalU_;
    PowerPath feedA_;
    PowerPath feedB_;
    std::vector<Server> servers_;

public:
    Rack(
        std::string id,
        int totalU,
        double feedCapacityKw
    )
        : id_(std::move(id)),
          totalU_(totalU),
          feedA_{"A", feedCapacityKw},
          feedB_{"B", feedCapacityKw} {}

    const std::string& id() const {
        return id_;
    }

    int usedU() const {
        int used = 0;

        for (const auto& server : servers_) {
            if (server.state != EquipmentState::Offline) {
                used += server.rackUnits;
            }
        }

        return used;
    }

    int freeU() const {
        return totalU_ - usedU();
    }

    double itLoadKw() const {
        double load = 0.0;

        for (const auto& server : servers_) {
            if (server.state != EquipmentState::Offline) {
                load += server.watts / 1000.0;
            }
        }

        return load;
    }

    void install(Server server) {
        if (server.rackUnits <= 0) {
            throw std::invalid_argument("Rack units must be positive.");
        }

        if (server.rackUnits > freeU()) {
            throw std::runtime_error(
                id_ + " does not have enough rack space for " + server.id
            );
        }

        const double loadKw = server.watts / 1000.0;

        if (server.dualPower) {
            /*
             * Dual-corded equipment is connected to separate electrical paths.
             * The simplified model divides nominal load equally between them.
             * The purpose is to evaluate survivability when one path fails.
             */
            const double halfLoad = loadKw / 2.0;

            if (!feedA_.canAccept(halfLoad) || !feedB_.canAccept(halfLoad)) {
                throw std::runtime_error(
                    id_ + " lacks dual-feed electrical capacity for " + server.id
                );
            }

            feedA_.addLoad(halfLoad);
            feedB_.addLoad(halfLoad);
        } else {
            /*
             * Single-corded equipment is deliberately placed on feed A.
             * Such equipment has no electrical-path redundancy.
             */
            feedA_.addLoad(loadKw);
        }

        servers_.push_back(std::move(server));
    }

    std::vector<std::string> failFeed(Feed feed) {
        PowerPath& failedPath = (feed == Feed::A) ? feedA_ : feedB_;
        failedPath.online = false;

        std::vector<std::string> affected;

        for (auto& server : servers_) {
            if (server.state == EquipmentState::Offline) {
                continue;
            }

            if (!server.dualPower) {
                /*
                 * The case study assumes single-corded devices use feed A.
                 * If A fails, they become unavailable. Dual-corded servers
                 * remain online because their second feed survives.
                 */
                if (feed == Feed::A) {
                    server.state = EquipmentState::Offline;
                    affected.push_back(server.id);
                }
            }
        }

        return affected;
    }

    void restoreFeed(Feed feed) {
        PowerPath& restoredPath = (feed == Feed::A) ? feedA_ : feedB_;
        restoredPath.online = true;

        /*
         * Recovery behavior is a policy choice. This model assumes an
         * operator can restore the single-corded device to service.
         */
        for (auto& server : servers_) {
            if (server.state == EquipmentState::Offline) {
                server.state = EquipmentState::Online;
            }
        }
    }

    const std::vector<Server>& servers() const {
        return servers_;
    }

    void print() const {
        std::cout << "Rack " << id_
                  << ": " << usedU() << "/" << totalU_
                  << "U, Feed A " << std::fixed << std::setprecision(2)
                  << feedA_.loadKw << " kW, Feed B "
                  << feedB_.loadKw << " kW\n";

        for (const auto& server : servers_) {
            std::cout << "  " << server.id
                      << " | " << server.name
                      << " | " << server.watts << " W"
                      << " | dual-power=" << std::boolalpha
                      << server.dualPower
                      << " | state=";

            if (server.state == EquipmentState::Online) {
                std::cout << "online";
            } else if (server.state == EquipmentState::Offline) {
                std::cout << "offline";
            } else {
                std::cout << "maintenance";
            }

            std::cout << '\n';
        }
    }
};

struct CoolingUnit {
    std::string id;
    double capacityKw;
    bool online{true};
};

class DataCenter {
private:
    std::string name_;
    std::map<std::string, Rack> racks_;
    std::map<std::string, CoolingUnit> cooling_;
    double ambientTemperatureC_{22.0};
    double maximumTemperatureC_{27.0};

public:
    explicit DataCenter(std::string name)
        : name_(std::move(name)) {}

    void addRack(Rack rack) {
        const auto key = rack.id();

        if (racks_.contains(key)) {
            throw std::invalid_argument("Duplicate rack: " + key);
        }

        racks_.emplace(key, std::move(rack));
    }

    void addCoolingUnit(CoolingUnit unit) {
        if (cooling_.contains(unit.id)) {
            throw std::invalid_argument(
                "Duplicate cooling unit: " + unit.id
            );
        }

        cooling_.emplace(unit.id, std::move(unit));
    }

    Rack& rack(const std::string& id) {
        auto iterator = racks_.find(id);

        if (iterator == racks_.end()) {
            throw std::out_of_range("Rack not found: " + id);
        }

        return iterator->second;
    }

    double totalITLoadKw() const {
        double total = 0.0;

        for (const auto& [id, rack] : racks_) {
            total += rack.itLoadKw();
        }

        return total;
    }

    double coolingCapacityKw() const {
        double total = 0.0;

        for (const auto& [id, unit] : cooling_) {
            if (unit.online) {
                total += unit.capacityKw;
            }
        }

        return total;
    }

    bool coolingSufficient() const {
        return coolingCapacityKw() >= totalITLoadKw();
    }

    bool temperatureSafe() const {
        return ambientTemperatureC_ <= maximumTemperatureC_;
    }

    bool nPlusOneCooling() const {
        std::vector<double> capacities;

        for (const auto& [id, unit] : cooling_) {
            if (unit.online) {
                capacities.push_back(unit.capacityKw);
            }
        }

        if (capacities.size() < 2) {
            return false;
        }

        const double total =
            std::accumulate(capacities.begin(), capacities.end(), 0.0);

        const double largest =
            *std::max_element(capacities.begin(), capacities.end());

        return total - largest >= totalITLoadKw();
    }

    void setTemperature(double temperatureC) {
        if (temperatureC < -50.0 || temperatureC > 80.0) {
            throw std::invalid_argument(
                "Temperature is outside the simulator's physical input range."
            );
        }

        ambientTemperatureC_ = temperatureC;
    }

    void failCooling(const std::string& id) {
        auto iterator = cooling_.find(id);

        if (iterator == cooling_.end()) {
            throw std::out_of_range("Cooling unit not found: " + id);
        }

        iterator->second.online = false;
    }

    void restoreCooling(const std::string& id) {
        auto iterator = cooling_.find(id);

        if (iterator == cooling_.end()) {
            throw std::out_of_range("Cooling unit not found: " + id);
        }

        iterator->second.online = true;
    }

    void report() const {
        std::cout << "\n=== " << name_ << " ===\n";
        std::cout << "IT load: " << std::fixed << std::setprecision(2)
                  << totalITLoadKw() << " kW\n";
        std::cout << "Cooling capacity: " << coolingCapacityKw() << " kW\n";
        std::cout << "Cooling sufficient: "
                  << std::boolalpha << coolingSufficient() << '\n';
        std::cout << "Cooling N+1: " << nPlusOneCooling() << '\n';
        std::cout << "Temperature safe: " << temperatureSafe() << '\n';

        for (const auto& [id, rack] : racks_) {
            rack.print();
        }
    }
};

int main() {
    try {
        DataCenter facility("North Campus Enterprise Data Center");

        facility.addRack(Rack("R01", 42, 10.0));
        facility.addRack(Rack("R02", 42, 10.0));
        facility.addRack(Rack("R03", 42, 10.0));

        facility.addCoolingUnit({"CRAC-01", 8.0, true});
        facility.addCoolingUnit({"CRAC-02", 8.0, true});
        facility.addCoolingUnit({"CRAC-03", 8.0, true});

        facility.rack("R01").install({
            "SRV-001",
            "Virtualization Host",
            2,
            900.0,
            true
        });

        facility.rack("R01").install({
            "SRV-002",
            "Database Host",
            2,
            750.0,
            true
        });

        facility.rack("R01").install({
            "SRV-003",
            "Facilities Gateway",
            1,
            250.0,
            false
        });

        facility.rack("R02").install({
            "SRV-004",
            "Storage Controller",
            2,
            700.0,
            true
        });

        facility.rack("R03").install({
            "SRV-005",
            "High Density Compute",
            4,
            1400.0,
            true
        });

        std::cout << "Initial physical infrastructure state:";
        facility.report();

        std::cout << "\n=== POWER PATH FAILURE ===\n";
        auto affected = facility.rack("R01").failFeed(Feed::A);

        std::cout << "Single-corded equipment affected: ";
        if (affected.empty()) {
            std::cout << "none";
        } else {
            for (const auto& id : affected) {
                std::cout << id << ' ';
            }
        }
        std::cout << '\n';

        facility.report();

        facility.rack("R01").restoreFeed(Feed::A);

        std::cout << "\n=== COOLING FAILURE ===\n";
        facility.failCooling("CRAC-01");
        facility.report();

        std::cout << "\n=== TEMPERATURE EXCURSION ===\n";
        facility.setTemperature(30.0);
        facility.report();

        std::cout << "\n=== RECOVERY ===\n";
        facility.restoreCooling("CRAC-01");
        facility.setTemperature(22.0);
        facility.report();

        std::cout << "\n=== ENGINEERING CAPACITY CHECK ===\n";
        const double projectedLoad = facility.totalITLoadKw() * 1.30;
        const double coolingCapacity = facility.coolingCapacityKw();

        std::cout << "Projected IT load at 30% growth: "
                  << projectedLoad << " kW\n";
        std::cout << "Current cooling capacity: "
                  << coolingCapacity << " kW\n";

        if (projectedLoad <= coolingCapacity) {
            std::cout << "Projected load fits current cooling capacity.\n";
        } else {
            std::cout << "Projected load requires additional cooling capacity.\n";
        }

    } catch (const std::exception& error) {
        std::cerr << "Infrastructure simulation error: "
                  << error.what() << '\n';
        return 1;
    }

    return 0;
}
