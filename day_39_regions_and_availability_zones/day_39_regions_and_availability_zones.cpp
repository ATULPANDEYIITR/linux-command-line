#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

using namespace std;

struct Region {
    string id;
    string residencyGroup;
    vector<string> zoneIds;
    bool healthy = true;
};

struct Zone {
    string id;
    string regionId;
    int capacity;
    int used = 0;
    double latencyMs;
    bool healthy = true;

    int freeCapacity() const {
        return healthy ? capacity - used : 0;
    }
};

struct Workload {
    string id;
    int requiredUnits;
    int minimumZones;
    double maximumLatencyMs;
    string residencyGroup;
    map<string, int> placement;
};

struct Evaluation {
    int survivingUnits = 0;
    int survivingZones = 0;
    bool capacitySatisfied = false;
    bool zoneSpreadSatisfied = false;
};

class GovernanceEngine {
private:
    map<string, Region> regions;
    map<string, Zone> zones;

public:
    void addRegion(const Region& region) {
        if (region.id.empty() || regions.count(region.id)) {
            throw invalid_argument("Region identifier is empty or duplicated.");
        }
        regions.emplace(region.id, region);
    }

    void addZone(const Zone& zone) {
        if (zone.id.empty() || zones.count(zone.id)) {
            throw invalid_argument("Zone identifier is empty or duplicated.");
        }
        auto region = regions.find(zone.regionId);
        if (region == regions.end()) {
            throw invalid_argument("Zone references an unknown region.");
        }
        if (region->second.residencyGroup != zone.id.substr(0, 0) &&
            region->second.residencyGroup.empty()) {
            throw invalid_argument("Region residency group is invalid.");
        }
        if (zone.capacity < 0 || zone.latencyMs < 0) {
            throw invalid_argument("Zone capacity and latency must be non-negative.");
        }
        zones.emplace(zone.id, zone);
        regions.at(zone.regionId).zoneIds.push_back(zone.id);
    }

    vector<string> eligibleZones(
        const Workload& workload,
        const set<string>& allowedRegions
    ) const {
        vector<string> candidates;

        for (const auto& [id, zone] : zones) {
            const Region& region = regions.at(zone.regionId);

            if (allowedRegions.count(zone.regionId) &&
                zone.healthy && region.healthy &&
                zone.latencyMs <= workload.maximumLatencyMs &&
                region.residencyGroup == workload.residencyGroup) {
                candidates.push_back(id);
            }
        }

        // Deterministic ordering makes simulation results reproducible.
        sort(candidates.begin(), candidates.end(), [&](const string& left,
                                                       const string& right) {
            const Zone& a = zones.at(left);
            const Zone& b = zones.at(right);
            if (a.latencyMs != b.latencyMs) return a.latencyMs < b.latencyMs;
            if (a.freeCapacity() != b.freeCapacity()) {
                return a.freeCapacity() > b.freeCapacity();
            }
            return a.id < b.id;
        });

        return candidates;
    }

    void deploy(Workload& workload, const set<string>& allowedRegions) {
        if (workload.requiredUnits <= 0 || workload.minimumZones <= 0) {
            throw invalid_argument("Workload capacity and minimum zone count must be positive.");
        }
        if (!workload.placement.empty()) {
            throw invalid_argument("Workload already has a placement.");
        }

        const auto candidates = eligibleZones(workload, allowedRegions);
        if (static_cast<int>(candidates.size()) < workload.minimumZones) {
            throw runtime_error("Insufficient eligible independent zones.");
        }

        map<string, int> planned;
        int remaining = workload.requiredUnits;

        for (const string& id : candidates) {
            if (static_cast<int>(planned.size()) < workload.minimumZones &&
                remaining > 0) {
                planned[id] = 1;
                --remaining;
            }
        }

        for (const string& id : candidates) {
            if (remaining == 0) break;

            const int alreadyPlanned = planned[id];
            const int available = zones.at(id).freeCapacity() - alreadyPlanned;
            const int addition = min(remaining, max(0, available));

            if (addition > 0) {
                planned[id] += addition;
                remaining -= addition;
            }
        }

        if (remaining > 0) {
            throw runtime_error("Insufficient aggregate capacity.");
        }

        // Validate the entire plan before mutating any zone.
        for (const auto& [id, units] : planned) {
            if (!zones.at(id).healthy ||
                units > zones.at(id).freeCapacity()) {
                throw runtime_error("Placement became invalid before reservation.");
            }
        }

        for (const auto& [id, units] : planned) {
            zones.at(id).used += units;
        }
        workload.placement = move(planned);
    }

    void failZone(const string& zoneId) {
        if (!zones.count(zoneId)) throw invalid_argument("Unknown zone.");
        zones.at(zoneId).healthy = false;
    }

    void recoverZone(const string& zoneId) {
        if (!zones.count(zoneId)) throw invalid_argument("Unknown zone.");
        zones.at(zoneId).healthy = true;
    }

    void failRegion(const string& regionId) {
        if (!regions.count(regionId)) throw invalid_argument("Unknown region.");
        regions.at(regionId).healthy = false;
        for (const string& zoneId : regions.at(regionId).zoneIds) {
            zones.at(zoneId).healthy = false;
        }
    }

    void recoverRegion(const string& regionId) {
        if (!regions.count(regionId)) throw invalid_argument("Unknown region.");
        regions.at(regionId).healthy = true;
        for (const string& zoneId : regions.at(regionId).zoneIds) {
            zones.at(zoneId).healthy = true;
        }
    }

    Evaluation evaluate(const Workload& workload) const {
        Evaluation result;

        for (const auto& [zoneId, units] : workload.placement) {
            const Zone& zone = zones.at(zoneId);
            if (zone.healthy) {
                result.survivingUnits += units;
                if (units > 0) ++result.survivingZones;
            }
        }

        result.capacitySatisfied =
            result.survivingUnits >= workload.requiredUnits;
        result.zoneSpreadSatisfied =
            result.survivingZones >= workload.minimumZones;

        return result;
    }

    void printReport() const {
        for (const auto& [regionId, region] : regions) {
            cout << "Region " << regionId
                 << " [" << (region.healthy ? "healthy" : "FAILED") << "]\n";

            for (const string& zoneId : region.zoneIds) {
                const Zone& zone = zones.at(zoneId);
                cout << "  " << zone.id
                     << " [" << (zone.healthy ? "healthy" : "FAILED") << "]"
                     << " capacity=" << zone.freeCapacity()
                     << "/" << zone.capacity
                     << " latency=" << zone.latencyMs << " ms\n";
            }
        }
    }
};

double haversineKm(double lat1, double lon1, double lat2, double lon2) {
    constexpr double earthRadiusKm = 6371.0;
    constexpr double pi = 3.14159265358979323846;

    auto radians = [pi](double degrees) { return degrees * pi / 180.0; };

    const double dLat = radians(lat2 - lat1);
    const double dLon = radians(lon2 - lon1);
    const double a =
        pow(sin(dLat / 2), 2) +
        cos(radians(lat1)) * cos(radians(lat2)) *
        pow(sin(dLon / 2), 2);

    return earthRadiusKm * 2 * asin(sqrt(min(1.0, max(0.0, a))));
}

int main() {
    try {
        GovernanceEngine engine;

        engine.addRegion({"india-west", "india", {}});
        engine.addRegion({"india-south", "india", {}});
        engine.addRegion({"singapore", "apac", {}});

        engine.addZone({"west-a", "india-west", 8, 0, 10});
        engine.addZone({"west-b", "india-west", 8, 0, 13});
        engine.addZone({"west-c", "india-west", 8, 0, 16});

        engine.addZone({"south-a", "india-south", 10, 0, 22});
        engine.addZone({"south-b", "india-south", 10, 0, 25});
        engine.addZone({"south-c", "india-south", 10, 0, 27});

        engine.addZone({"sg-a", "singapore", 12, 0, 55});
        engine.addZone({"sg-b", "singapore", 12, 0, 58});

        Workload payments{
            "payment-ledger", 9, 3, 30, "india", {}
        };

        engine.deploy(payments, {"india-west"});
        cout << "Initial placement:\n";
        for (const auto& [zone, units] : payments.placement) {
            cout << "  " << zone << ": " << units << " units\n";
        }

        engine.failZone("west-b");
        Evaluation zoneFailure = engine.evaluate(payments);
        cout << "\nAfter a single-zone outage:\n"
             << "  surviving units: " << zoneFailure.survivingUnits << "\n"
             << "  surviving zones: " << zoneFailure.survivingZones << "\n"
             << "  capacity preserved: "
             << boolalpha << zoneFailure.capacitySatisfied << "\n";

        engine.recoverZone("west-b");
        engine.failRegion("india-west");

        Evaluation regionalFailure = engine.evaluate(payments);
        cout << "\nAfter a regional outage:\n"
             << "  surviving units: " << regionalFailure.survivingUnits << "\n"
             << "  capacity preserved: " << regionalFailure.capacitySatisfied << "\n";

        engine.recoverRegion("india-west");

        Workload restricted{"restricted-records", 4, 2, 30, "india", {}};
        try {
            engine.deploy(restricted, {"singapore"});
        } catch (const exception& error) {
            cout << "\nPlacement rejected: " << error.what() << "\n";
        }

        const double distance = haversineKm(19.0760, 72.8777, 1.3521, 103.8198);
        cout << fixed << setprecision(0)
             << "\nApproximate Mumbai-Singapore distance: "
             << distance << " km\n";

        cout << "\nInfrastructure inventory:\n";
        engine.printReport();
    } catch (const exception& error) {
        cerr << "Infrastructure simulation failed: " << error.what() << "\n";
        return 1;
    }

    return 0;
}
