#include <algorithm>
#include <array>
#include <chrono>
#include <cctype>
#include <ctime>
#include <iomanip>
#include <iostream>
#include <map>
#include <memory>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

using namespace std;

// =========================================================
// CLOUD SECURITY MONITORING
// C++17
//
// Governance-oriented security monitoring engine.
//
// Capabilities:
// - Cloud audit event processing
// - Identity and access monitoring
// - Sliding-window detection
// - Anomaly scoring
// - Security alert generation
// - Incident management
// - Evidence tracking
// - Protected resource policies
// - Merge-free, deterministic rule evaluation
//
// Standard library only.
// =========================================================

enum class EventType {
    LOGIN,
    FAILED_LOGIN,
    LOGOUT,
    API_ACCESS,
    PERMISSION_CHANGE,
    RESOURCE_CREATED,
    RESOURCE_DELETED,
    CONFIGURATION_CHANGE,
    DATA_ACCESS,
    SECRET_ACCESS,
    NETWORK_ACCESS
};

enum class Severity {
    LOW,
    MEDIUM,
    HIGH,
    CRITICAL
};

enum class IncidentStatus {
    OPEN,
    INVESTIGATING,
    CONTAINED,
    RESOLVED,
    CLOSED
};


string toString(EventType type) {
    switch (type) {
        case EventType::LOGIN: return "LOGIN";
        case EventType::FAILED_LOGIN: return "FAILED_LOGIN";
        case EventType::LOGOUT: return "LOGOUT";
        case EventType::API_ACCESS: return "API_ACCESS";
        case EventType::PERMISSION_CHANGE: return "PERMISSION_CHANGE";
        case EventType::RESOURCE_CREATED: return "RESOURCE_CREATED";
        case EventType::RESOURCE_DELETED: return "RESOURCE_DELETED";
        case EventType::CONFIGURATION_CHANGE: return "CONFIGURATION_CHANGE";
        case EventType::DATA_ACCESS: return "DATA_ACCESS";
        case EventType::SECRET_ACCESS: return "SECRET_ACCESS";
        case EventType::NETWORK_ACCESS: return "NETWORK_ACCESS";
    }

    throw invalid_argument("Unknown event type.");
}


string toString(Severity severity) {
    switch (severity) {
        case Severity::LOW: return "LOW";
        case Severity::MEDIUM: return "MEDIUM";
        case Severity::HIGH: return "HIGH";
        case Severity::CRITICAL: return "CRITICAL";
    }

    throw invalid_argument("Unknown severity.");
}


string toString(IncidentStatus status) {
    switch (status) {
        case IncidentStatus::OPEN: return "OPEN";
        case IncidentStatus::INVESTIGATING: return "INVESTIGATING";
        case IncidentStatus::CONTAINED: return "CONTAINED";
        case IncidentStatus::RESOLVED: return "RESOLVED";
        case IncidentStatus::CLOSED: return "CLOSED";
    }

    throw invalid_argument("Unknown incident status.");
}


// =========================================================
// DOMAIN MODEL
// =========================================================

struct SecurityEvent {
    string id;
    long long timestamp;
    EventType type;
    string userId;
    string sourceIp;
    string resource;
    string action;
    bool success;
    string region;
    bool approved = false;
    bool mfa = false;
    int sensitivity = 1;
};


struct SecurityAlert {
    string id;
    string ruleId;
    string userId;
    string eventId;
    Severity severity;
    int riskScore;
    string description;
    long long timestamp;
};


struct SecurityIncident {
    string id;
    string title;
    Severity severity;
    IncidentStatus status;
    vector<string> alertIds;
    vector<string> evidenceHashes;
    vector<string> notes;
    string assignedAnalyst;
    long long createdAt;
    long long updatedAt;
};


// =========================================================
// UTILITY FUNCTIONS
// =========================================================

string generateId(const string& prefix, int value) {
    return prefix + "-" + to_string(value);
}


Severity classifySeverity(int score) {
    if (score >= 90) return Severity::CRITICAL;
    if (score >= 70) return Severity::HIGH;
    if (score >= 40) return Severity::MEDIUM;
    return Severity::LOW;
}


bool validIdentifier(const string& value) {
    if (value.empty() || value.size() > 256) {
        return false;
    }

    return all_of(
        value.begin(),
        value.end(),
        [](unsigned char c) {
            return isalnum(c) ||
                   c == '-' ||
                   c == '_' ||
                   c == '.' ||
                   c == ':';
        }
    );
}


bool validIPv4(const string& ip) {
    stringstream stream(ip);
    string segment;
    int count = 0;

    while (getline(stream, segment, '.')) {
        if (segment.empty() || segment.size() > 3) {
            return false;
        }

        if (segment.size() > 1 && segment[0] == '0') {
            return false;
        }

        if (!all_of(
            segment.begin(),
            segment.end(),
            [](unsigned char c) {
                return isdigit(c);
            }
        )) {
            return false;
        }

        int value = stoi(segment);

        if (value > 255) return false;

        count++;
    }

    return count == 4;
}


void validateEvent(const SecurityEvent& event) {
    if (!validIdentifier(event.id)) {
        throw invalid_argument("Invalid event identifier.");
    }

    if (!validIdentifier(event.userId)) {
        throw invalid_argument("Invalid user identifier.");
    }

    if (!validIPv4(event.sourceIp)) {
        throw invalid_argument("Invalid IPv4 address.");
    }

    if (
        event.resource.empty() ||
        event.action.empty() ||
        event.region.empty()
    ) {
        throw invalid_argument("Missing event attributes.");
    }

    if (event.timestamp <= 0) {
        throw invalid_argument("Invalid event timestamp.");
    }

    if (event.sensitivity < 1 || event.sensitivity > 5) {
        throw invalid_argument("Invalid resource sensitivity.");
    }
}


// =========================================================
// WINDOW COUNTER
// =========================================================

class SlidingWindowCounter {
private:
    unordered_map<string, vector<long long>> events;
    long long windowSeconds;

public:
    explicit SlidingWindowCounter(long long window)
        : windowSeconds(window) {

        if (window <= 0) {
            throw invalid_argument("Window must be positive.");
        }
    }

    size_t add(
        const string& key,
        long long timestamp
    ) {
        auto& values = events[key];

        values.push_back(timestamp);

        long long cutoff = timestamp - windowSeconds;

        auto firstValid = lower_bound(
            values.begin(),
            values.end(),
            cutoff
        );

        values.erase(values.begin(), firstValid);

        return values.size();
    }
};


// =========================================================
// BASELINE SERVICE
// =========================================================

class BehavioralBaseline {
private:
    unordered_map<string, unordered_set<string>> knownIPs;
    unordered_map<string, unordered_set<int>> knownHours;

public:
    void observe(const SecurityEvent& event) {
        if (!event.success) return;

        knownIPs[event.userId].insert(event.sourceIp);

        time_t timestamp = static_cast<time_t>(
            event.timestamp
        );

        tm* utc = gmtime(&timestamp);

        if (utc != nullptr) {
            knownHours[event.userId].insert(utc->tm_hour);
        }
    }

    bool unfamiliarIP(const SecurityEvent& event) const {
        auto it = knownIPs.find(event.userId);

        if (
            it == knownIPs.end() ||
            it->second.empty()
        ) {
            return false;
        }

        return !it->second.count(event.sourceIp);
    }

    bool unusualHour(const SecurityEvent& event) const {
        auto it = knownHours.find(event.userId);

        if (
            it == knownHours.end() ||
            it->second.empty()
        ) {
            return false;
        }

        time_t timestamp = static_cast<time_t>(
            event.timestamp
        );

        tm* utc = gmtime(&timestamp);

        if (utc == nullptr) return false;

        return !it->second.count(utc->tm_hour);
    }
};


// =========================================================
// SECURITY POLICY
// =========================================================

struct MonitoringPolicy {
    size_t failedLoginThreshold = 5;
    size_t permissionChangeThreshold = 3;
    long long failedLoginWindow = 600;
    long long permissionWindow = 900;
    int minimumMfaSensitivity = 4;
    int criticalRiskThreshold = 90;
    bool requireApprovedPrivilegeChanges = true;
};


class ResourcePolicy {
private:
    unordered_map<string, int> resourceSensitivity;

public:
    void registerResource(
        const string& resource,
        int sensitivity
    ) {
        if (
            resource.empty() ||
            sensitivity < 1 ||
            sensitivity > 5
        ) {
            throw invalid_argument(
                "Invalid resource policy."
            );
        }

        resourceSensitivity[resource] = sensitivity;
    }

    int sensitivityOf(const string& resource) const {
        auto it = resourceSensitivity.find(resource);

        if (it == resourceSensitivity.end()) {
            return 1;
        }

        return it->second;
    }

    bool requiresMFA(const string& resource) const {
        return sensitivityOf(resource) >= 4;
    }
};


// =========================================================
// DETECTION ENGINE
// =========================================================

class DetectionEngine {
private:
    MonitoringPolicy policy;
    SlidingWindowCounter failedLogins;
    SlidingWindowCounter permissionChanges;
    BehavioralBaseline baseline;

    int nextAlertId = 1;

    vector<SecurityAlert> alerts;

    SecurityAlert createAlert(
        const SecurityEvent& event,
        const string& rule,
        int score,
        const string& description
    ) {
        score = min(100, max(0, score));

        SecurityAlert alert{
            generateId("ALERT", nextAlertId++),
            rule,
            event.userId,
            event.id,
            classifySeverity(score),
            score,
            description,
            event.timestamp
        };

        alerts.push_back(alert);

        return alert;
    }

public:
    explicit DetectionEngine(
        MonitoringPolicy configuration = {}
    )
        : policy(configuration),
          failedLogins(configuration.failedLoginWindow),
          permissionChanges(configuration.permissionWindow) {}

    vector<SecurityAlert> evaluate(
        const SecurityEvent& event,
        const ResourcePolicy& resources
    ) {
        vector<SecurityAlert> generated;

        if (event.type == EventType::FAILED_LOGIN) {
            size_t count = failedLogins.add(
                event.userId,
                event.timestamp
            );

            if (count >= policy.failedLoginThreshold) {
                generated.push_back(
                    createAlert(
                        event,
                        "AUTH-001",
                        85,
                        "Repeated failed authentication attempts."
                    )
                );
            }
        }

        if (event.type == EventType::PERMISSION_CHANGE) {
            size_t count = permissionChanges.add(
                event.userId,
                event.timestamp
            );

            if (count >= policy.permissionChangeThreshold) {
                generated.push_back(
                    createAlert(
                        event,
                        "IAM-001",
                        95,
                        "Rapid privilege modifications."
                    )
                );
            }

            if (
                policy.requireApprovedPrivilegeChanges &&
                !event.approved
            ) {
                generated.push_back(
                    createAlert(
                        event,
                        "IAM-002",
                        95,
                        "Unapproved privilege modification."
                    )
                );
            }
        }

        if (
            event.success &&
            baseline.unfamiliarIP(event)
        ) {
            generated.push_back(
                createAlert(
                    event,
                    "ANOM-001",
                    75,
                    "Successful access from unfamiliar IP."
                )
            );
        }

        if (
            event.success &&
            baseline.unusualHour(event)
        ) {
            generated.push_back(
                createAlert(
                    event,
                    "ANOM-002",
                    65,
                    "Access outside observed time baseline."
                )
            );
        }

        if (
            event.type == EventType::SECRET_ACCESS &&
            event.success &&
            !event.approved
        ) {
            generated.push_back(
                createAlert(
                    event,
                    "DATA-001",
                    95,
                    "Unapproved sensitive secret access."
                )
            );
        }

        if (
            event.success &&
            resources.requiresMFA(event.resource) &&
            !event.mfa
        ) {
            generated.push_back(
                createAlert(
                    event,
                    "IAM-003",
                    90,
                    "Sensitive resource accessed without MFA."
                )
            );
        }

        baseline.observe(event);

        return generated;
    }

    const vector<SecurityAlert>& getAlerts() const {
        return alerts;
    }
};


// =========================================================
// INCIDENT MANAGEMENT
// =========================================================

class IncidentService {
private:
    unordered_map<string, SecurityIncident> incidents;
    int nextIncidentId = 1;

    bool allowed(
        IncidentStatus current,
        IncidentStatus next
    ) const {
        switch (current) {
            case IncidentStatus::OPEN:
                return next == IncidentStatus::INVESTIGATING ||
                       next == IncidentStatus::CLOSED;

            case IncidentStatus::INVESTIGATING:
                return next == IncidentStatus::CONTAINED ||
                       next == IncidentStatus::RESOLVED ||
                       next == IncidentStatus::CLOSED;

            case IncidentStatus::CONTAINED:
                return next == IncidentStatus::INVESTIGATING ||
                       next == IncidentStatus::RESOLVED;

            case IncidentStatus::RESOLVED:
                return next == IncidentStatus::CLOSED ||
                       next == IncidentStatus::INVESTIGATING;

            case IncidentStatus::CLOSED:
                return false;
        }

        return false;
    }

public:
    SecurityIncident& create(
        const SecurityAlert& alert
    ) {
        string id = generateId(
            "INCIDENT",
            nextIncidentId++
        );

        SecurityIncident incident{
            id,
            alert.description,
            alert.severity,
            IncidentStatus::OPEN,
            {alert.id},
            {},
            {},
            "",
            alert.timestamp,
            alert.timestamp
        };

        auto result = incidents.emplace(
            id,
            move(incident)
        );

        return result.first->second;
    }

    void transition(
        const string& incidentId,
        IncidentStatus next,
        long long timestamp
    ) {
        auto it = incidents.find(incidentId);

        if (it == incidents.end()) {
            throw out_of_range("Incident not found.");
        }

        auto& incident = it->second;

        if (!allowed(incident.status, next)) {
            throw logic_error(
                "Invalid incident status transition."
            );
        }

        incident.status = next;
        incident.updatedAt = timestamp;
    }

    void assign(
        const string& incidentId,
        const string& analyst
    ) {
        auto it = incidents.find(incidentId);

        if (it == incidents.end()) {
            throw out_of_range("Incident not found.");
        }

        if (!validIdentifier(analyst)) {
            throw invalid_argument("Invalid analyst identifier.");
        }

        if (it->second.status == IncidentStatus::CLOSED) {
            throw logic_error("Incident is closed.");
        }

        it->second.assignedAnalyst = analyst;
    }

    void addEvidence(
        const string& incidentId,
        const string& evidence
    ) {
        auto it = incidents.find(incidentId);

        if (it == incidents.end()) {
            throw out_of_range("Incident not found.");
        }

        if (
            evidence.empty() ||
            evidence.size() > 100000
        ) {
            throw invalid_argument("Invalid evidence.");
        }

        if (it->second.status == IncidentStatus::CLOSED) {
            throw logic_error(
                "Closed incidents cannot accept evidence."
            );
        }

        // Evidence is identified by a deterministic content fingerprint.
        // Production systems should use a cryptographic hash library.
        hash<string> hasher;

        string fingerprint = to_string(
            hasher(evidence)
        );

        it->second.evidenceHashes.push_back(fingerprint);
    }

    void addNote(
        const string& incidentId,
        const string& note
    ) {
        auto it = incidents.find(incidentId);

        if (it == incidents.end()) {
            throw out_of_range("Incident not found.");
        }

        if (note.empty() || note.size() > 5000) {
            throw invalid_argument("Invalid investigation note.");
        }

        if (it->second.status == IncidentStatus::CLOSED) {
            throw logic_error("Incident is closed.");
        }

        it->second.notes.push_back(note);
    }

    const unordered_map<string, SecurityIncident>&
    getIncidents() const {
        return incidents;
    }
};


// =========================================================
// CENTRAL MONITORING PLATFORM
// =========================================================

class CloudSecurityPlatform {
private:
    MonitoringPolicy policy;
    ResourcePolicy resourcePolicies;
    DetectionEngine detector;
    IncidentService incidentService;

    vector<SecurityEvent> auditEvents;
    unordered_set<string> processedEventIds;

    int nextEventId = 1;

public:
    explicit CloudSecurityPlatform(
        MonitoringPolicy configuration = {}
    )
        : policy(configuration),
          detector(configuration) {

        resourcePolicies.registerResource(
            "production/database",
            5
        );

        resourcePolicies.registerResource(
            "production/iam",
            5
        );

        resourcePolicies.registerResource(
            "development/logs",
            2
        );
    }

    vector<SecurityAlert> ingest(
        const SecurityEvent& event
    ) {
        validateEvent(event);

        if (processedEventIds.count(event.id)) {
            throw invalid_argument("Duplicate event identifier.");
        }

        // Record the event before applying detection rules.
        auditEvents.push_back(event);
        processedEventIds.insert(event.id);

        vector<SecurityAlert> alerts = detector.evaluate(
            event,
            resourcePolicies
        );

        for (const auto& alert : alerts) {
            incidentService.create(alert);
        }

        return alerts;
    }

    void printReport() const {
        map<string, int> severityCounts;
        map<string, int> eventCounts;

        for (const auto& event : auditEvents) {
            eventCounts[toString(event.type)]++;
        }

        for (const auto& alert : detector.getAlerts()) {
            severityCounts[toString(alert.severity)]++;
        }

        cout << "\nCLOUD SECURITY MONITORING REPORT\n";
        cout << "========================================\n";

        cout << "Total audit events: "
             << auditEvents.size() << '\n';

        cout << "Total alerts: "
             << detector.getAlerts().size() << '\n';

        cout << "Total incidents: "
             << incidentService.getIncidents().size() << '\n';

        cout << "\nEvents by type:\n";

        for (const auto& [type, count] : eventCounts) {
            cout << "  " << type << ": " << count << '\n';
        }

        cout << "\nAlerts by severity:\n";

        for (const auto& [severity, count] : severityCounts) {
            cout << "  " << severity << ": " << count << '\n';
        }

        cout << "\nSecurity alerts:\n";

        for (const auto& alert : detector.getAlerts()) {
            cout << alert.id
                 << " | " << alert.ruleId
                 << " | " << toString(alert.severity)
                 << " | " << alert.riskScore
                 << " | " << alert.description
                 << '\n';
        }

        cout << "\nIncident states:\n";

        for (
            const auto& [id, incident] :
            incidentService.getIncidents()
        ) {
            cout << id
                 << " | " << toString(incident.severity)
                 << " | " << toString(incident.status)
                 << '\n';
        }
    }

    IncidentService& incidents() {
        return incidentService;
    }

    const vector<SecurityEvent>& auditTrail() const {
        return auditEvents;
    }
};


// =========================================================
// TEST DATA
// =========================================================

vector<SecurityEvent> createSampleEvents() {
    const long long now = 1794396000LL;

    vector<SecurityEvent> events;

    // Historical baseline.
    for (int i = 0; i < 3; i++) {
        events.push_back({
            generateId("EVT", i + 1),
            now - 86400LL * 3 + i * 3600LL,
            EventType::LOGIN,
            "cloud-admin",
            "10.10.1.10",
            "production/iam",
            "authenticate",
            true,
            "ap-south-1",
            true,
            true,
            5
        });
    }

    // Repeated failed authentication.
    for (int i = 0; i < 6; i++) {
        events.push_back({
            generateId("EVT", i + 4),
            now + i * 30LL,
            EventType::FAILED_LOGIN,
            "cloud-admin",
            "203.0.113.25",
            "production/iam",
            "authenticate",
            false,
            "ap-south-1",
            false,
            false,
            5
        });
    }

    // Unapproved privilege escalation.
    events.push_back({
        "EVT-10",
        now + 400,
        EventType::PERMISSION_CHANGE,
        "cloud-admin",
        "203.0.113.25",
        "production/iam",
        "grant_admin",
        true,
        "ap-south-1",
        false,
        false,
        5
    });

    // Unapproved secret access.
    events.push_back({
        "EVT-11",
        now + 500,
        EventType::SECRET_ACCESS,
        "service-account",
        "198.51.100.40",
        "production/database",
        "read_secret",
        true,
        "ap-south-1",
        false,
        false,
        5
    });

    return events;
}


// =========================================================
// TEST SUITE
// =========================================================

void runTests(CloudSecurityPlatform& platform) {
    if (platform.auditTrail().size() != 11) {
        throw runtime_error("Audit count test failed.");
    }

    if (platform.auditTrail().empty()) {
        throw runtime_error("Audit trail is empty.");
    }

    bool rejected = false;

    try {
        SecurityEvent invalid{
            "INVALID",
            1794396000LL,
            EventType::LOGIN,
            "user",
            "999.999.999.999",
            "resource",
            "login",
            true,
            "region"
        };

        validateEvent(invalid);

    } catch (const invalid_argument&) {
        rejected = true;
    }

    if (!rejected) {
        throw runtime_error("IP validation test failed.");
    }

    SlidingWindowCounter counter(600);

    counter.add("user", 1000);
    counter.add("user", 1100);

    if (counter.add("user", 1200) != 3) {
        throw runtime_error("Window counter test failed.");
    }

    if (counter.add("user", 1700) != 1) {
        throw runtime_error("Window expiry test failed.");
    }

    rejected = false;

    try {
        platform.ingest(platform.auditTrail().front());
    } catch (const invalid_argument&) {
        rejected = true;
    }

    if (!rejected) {
        throw runtime_error("Duplicate event test failed.");
    }

    cout << "\nAll C++17 monitoring tests passed.\n";
}


// =========================================================
// MAIN
// =========================================================

int main() {
    try {
        CloudSecurityPlatform platform;

        auto events = createSampleEvents();

        for (const auto& event : events) {
            platform.ingest(event);
        }

        platform.printReport();

        // Demonstrate an investigation lifecycle.
        if (!platform.incidents().getIncidents().empty()) {
            const auto& incidents =
                platform.incidents().getIncidents();

            const string incidentId =
                incidents.begin()->first;

            platform.incidents().assign(
                incidentId,
                "soc-analyst-01"
            );

            platform.incidents().transition(
                incidentId,
                IncidentStatus::INVESTIGATING,
                events.back().timestamp + 100
            );

            platform.incidents().addNote(
                incidentId,
                "Initial triage completed."
            );

            platform.incidents().addEvidence(
                incidentId,
                "Cloud audit evidence retained."
            );
        }

        runTests(platform);

        cout << "\nMonitoring execution completed.\n";

    } catch (const exception& error) {
        cerr << "Monitoring error: "
             << error.what() << '\n';

        return 1;
    }

    return 0;
}
