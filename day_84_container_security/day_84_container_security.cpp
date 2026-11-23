#include <algorithm>
#include <chrono>
#include <cctype>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

using namespace std;

// ============================================================
// 1. DOMAIN MODEL
// ============================================================

enum class Severity {
    CRITICAL,
    HIGH,
    MEDIUM,
    LOW,
    INFO
};

enum class FindingType {
    VULNERABILITY,
    MISCONFIGURATION,
    SECRET,
    COMPLIANCE
};

enum class DeploymentStatus {
    APPROVED,
    BLOCKED,
    REVIEW_REQUIRED
};

enum class ReviewStatus {
    OPEN,
    IN_PROGRESS,
    MITIGATED,
    RESOLVED,
    ACCEPTED_RISK
};

string toString(Severity severity) {
    switch (severity) {
        case Severity::CRITICAL: return "CRITICAL";
        case Severity::HIGH: return "HIGH";
        case Severity::MEDIUM: return "MEDIUM";
        case Severity::LOW: return "LOW";
        case Severity::INFO: return "INFO";
    }

    throw logic_error("Unknown severity");
}

string toString(DeploymentStatus status) {
    switch (status) {
        case DeploymentStatus::APPROVED: return "APPROVED";
        case DeploymentStatus::BLOCKED: return "BLOCKED";
        case DeploymentStatus::REVIEW_REQUIRED:
            return "REVIEW_REQUIRED";
    }

    throw logic_error("Unknown deployment status");
}

string toString(FindingType type) {
    switch (type) {
        case FindingType::VULNERABILITY: return "VULNERABILITY";
        case FindingType::MISCONFIGURATION: return "MISCONFIGURATION";
        case FindingType::SECRET: return "SECRET";
        case FindingType::COMPLIANCE: return "COMPLIANCE";
    }

    throw logic_error("Unknown finding type");
}

// ============================================================
// 2. DOMAIN STRUCTURES
// ============================================================

struct Package {
    string name;
    string version;
    string packageType = "APPLICATION";
};

struct Vulnerability {
    string cve;
    string package;
    string installedVersion;
    optional<string> fixedVersion;
    Severity severity;
    string description;
    bool exploitable = false;
};

struct ContainerImage {
    string name;
    string tag;
    string baseImage;

    vector<Package> packages;
    vector<Vulnerability> vulnerabilities;

    vector<int> exposedPorts;
    map<string, string> environment;

    string user = "root";
    vector<string> entrypoint;

    int layers = 1;
    double sizeMB = 100.0;

    bool signedImage = false;
    bool hasDigest = false;
    bool healthcheck = false;

    string reference() const {
        return name + ":" + tag;
    }
};

struct Finding {
    FindingType type;
    Severity severity;
    string resource;
    string description;
    string remediation;
};

struct SecurityPolicy {
    int maximumCritical = 0;
    int maximumHigh = 0;
    int maximumMedium = 3;

    bool requireNonRoot = true;
    bool requireSignature = true;
    bool requireDigest = true;
    bool requireHealthcheck = true;
    bool blockSecrets = true;
};

struct ScanReport {
    string imageReference;
    vector<Finding> findings;
    DeploymentStatus status;

    map<Severity, int> severityCounts() const {
        map<Severity, int> counts;

        for (const Finding& finding : findings) {
            counts[finding.severity]++;
        }

        return counts;
    }
};

// ============================================================
// 3. INPUT VALIDATION
// ============================================================

void validateImage(const ContainerImage& image) {
    if (image.name.empty() || image.tag.empty()) {
        throw invalid_argument(
            "Image name and tag are mandatory."
        );
    }

    if (image.baseImage.empty()) {
        throw invalid_argument("Base image is required.");
    }

    if (image.layers < 1 || image.sizeMB <= 0) {
        throw invalid_argument("Invalid image dimensions.");
    }

    set<int> ports;

    for (int port : image.exposedPorts) {
        if (port < 1 || port > 65535) {
            throw invalid_argument("Invalid exposed port.");
        }

        if (!ports.insert(port).second) {
            throw invalid_argument("Duplicate exposed port.");
        }
    }

    set<string> packageNames;

    for (const Package& package : image.packages) {
        if (package.name.empty() || package.version.empty()) {
            throw invalid_argument("Invalid package record.");
        }

        if (!packageNames.insert(package.name).second) {
            throw invalid_argument("Duplicate package.");
        }
    }
}

// ============================================================
// 4. IMAGE VULNERABILITY SCANNER
// ============================================================

class VulnerabilityScanner {

public:
    vector<Finding> scan(const ContainerImage& image) const {
        vector<Finding> findings;

        for (const Vulnerability& vulnerability :
             image.vulnerabilities) {

            string remediation;

            if (vulnerability.fixedVersion.has_value()) {
                remediation =
                    "Upgrade to version " +
                    vulnerability.fixedVersion.value();
            } else {
                remediation =
                    "Apply an approved mitigation or replace package.";
            }

            findings.push_back({
                FindingType::VULNERABILITY,
                vulnerability.severity,
                vulnerability.package,
                vulnerability.cve + ": " +
                    vulnerability.description,
                remediation
            });
        }

        return findings;
    }
};

// ============================================================
// 5. SECRET SCANNER
// ============================================================

class SecretScanner {

    static string lowercase(string value) {
        transform(
            value.begin(),
            value.end(),
            value.begin(),
            [](unsigned char c) {
                return static_cast<char>(tolower(c));
            }
        );

        return value;
    }

    static bool containsSecret(
        const string& key,
        const string& value
    ) {
        string combined = lowercase(key + "=" + value);

        const vector<string> indicators = {
            "password=",
            "passwd=",
            "secret=",
            "api_key=",
            "access_token=",
            "auth_token=",
            "-----begin private key-----",
            "-----begin rsa private key-----"
        };

        for (const string& indicator : indicators) {
            size_t position = combined.find(indicator);

            if (position != string::npos) {
                size_t valuePosition =
                    position + indicator.length();

                if (valuePosition < combined.length()) {
                    string candidate =
                        combined.substr(valuePosition);

                    if (candidate.size() >= 6 &&
                        candidate[0] != '$') {
                        return true;
                    }
                }
            }
        }

        return value.find("AKIA") == 0 &&
               value.size() == 20;
    }

public:
    vector<Finding> scan(const ContainerImage& image) const {
        vector<Finding> findings;

        for (const auto& [key, value] : image.environment) {
            if (containsSecret(key, value)) {
                findings.push_back({
                    FindingType::SECRET,
                    Severity::CRITICAL,
                    key,
                    "Potential credential exposure detected.",
                    "Remove and rotate the credential. "
                    "Use managed secret injection."
                });
            }
        }

        return findings;
    }
};

// ============================================================
// 6. IMAGE CONFIGURATION SCANNER
// ============================================================

class ConfigurationScanner {

public:
    vector<Finding> scan(
        const ContainerImage& image
    ) const {
        vector<Finding> findings;

        string user = image.user;

        transform(
            user.begin(),
            user.end(),
            user.begin(),
            [](unsigned char c) {
                return static_cast<char>(tolower(c));
            }
        );

        if (user == "root" || user == "0" || user == "0:0") {
            findings.push_back({
                FindingType::MISCONFIGURATION,
                Severity::HIGH,
                "USER",
                "Container runs as root.",
                "Configure a non-root runtime identity."
            });
        }

        if (image.sizeMB > 200) {
            findings.push_back({
                FindingType::MISCONFIGURATION,
                Severity::MEDIUM,
                "IMAGE_SIZE",
                "Image exceeds 200 MB.",
                "Use a minimal runtime base image."
            });
        }

        if (image.layers > 15) {
            findings.push_back({
                FindingType::MISCONFIGURATION,
                Severity::LOW,
                "IMAGE_LAYERS",
                "Excessive image layers.",
                "Reduce unnecessary build layers."
            });
        }

        if (!image.signedImage) {
            findings.push_back({
                FindingType::COMPLIANCE,
                Severity::HIGH,
                "SIGNATURE",
                "Image is not signed.",
                "Sign and verify image provenance."
            });
        }

        if (!image.hasDigest) {
            findings.push_back({
                FindingType::COMPLIANCE,
                Severity::MEDIUM,
                "DIGEST",
                "Immutable digest is missing.",
                "Record and deploy a verified image digest."
            });
        }

        if (!image.healthcheck) {
            findings.push_back({
                FindingType::MISCONFIGURATION,
                Severity::LOW,
                "HEALTHCHECK",
                "Health check is missing.",
                "Configure an application health check."
            });
        }

        if (image.entrypoint.empty()) {
            findings.push_back({
                FindingType::MISCONFIGURATION,
                Severity::MEDIUM,
                "ENTRYPOINT",
                "Explicit entrypoint is missing.",
                "Configure the application entrypoint."
            });
        }

        if (image.tag == "latest") {
            findings.push_back({
                FindingType::MISCONFIGURATION,
                Severity::MEDIUM,
                "TAG",
                "Mutable latest tag detected.",
                "Use a versioned tag and immutable digest."
            });
        }

        return findings;
    }
};

// ============================================================
// 7. POLICY EVALUATION ENGINE
// ============================================================

class PolicyEngine {

    SecurityPolicy policy;

public:
    explicit PolicyEngine(SecurityPolicy configuredPolicy)
        : policy(configuredPolicy) {

        if (policy.maximumCritical < 0 ||
            policy.maximumHigh < 0 ||
            policy.maximumMedium < 0) {
            throw invalid_argument(
                "Policy thresholds cannot be negative."
            );
        }
    }

    DeploymentStatus evaluate(
        const ContainerImage& image,
        const vector<Finding>& findings
    ) const {

        map<Severity, int> counts;

        for (const Finding& finding : findings) {
            counts[finding.severity]++;
        }

        if (counts[Severity::CRITICAL] >
            policy.maximumCritical) {
            return DeploymentStatus::BLOCKED;
        }

        if (counts[Severity::HIGH] >
            policy.maximumHigh) {
            return DeploymentStatus::BLOCKED;
        }

        if (counts[Severity::MEDIUM] >
            policy.maximumMedium) {
            return DeploymentStatus::BLOCKED;
        }

        if (policy.blockSecrets) {
            bool secretFound = any_of(
                findings.begin(),
                findings.end(),
                [](const Finding& finding) {
                    return finding.type == FindingType::SECRET;
                }
            );

            if (secretFound) {
                return DeploymentStatus::BLOCKED;
            }
        }

        string user = image.user;

        transform(
            user.begin(),
            user.end(),
            user.begin(),
            [](unsigned char c) {
                return static_cast<char>(tolower(c));
            }
        );

        if (policy.requireNonRoot &&
            (user == "root" || user == "0" || user == "0:0")) {
            return DeploymentStatus::BLOCKED;
        }

        if (policy.requireSignature && !image.signedImage) {
            return DeploymentStatus::BLOCKED;
        }

        if (policy.requireDigest && !image.hasDigest) {
            return DeploymentStatus::BLOCKED;
        }

        if (policy.requireHealthcheck && !image.healthcheck) {
            return DeploymentStatus::BLOCKED;
        }

        return DeploymentStatus::APPROVED;
    }
};

// ============================================================
// 8. REPOSITORY AND IMAGE GOVERNANCE
// ============================================================

class ContainerGovernanceEngine {

    VulnerabilityScanner vulnerabilityScanner;
    SecretScanner secretScanner;
    ConfigurationScanner configurationScanner;
    PolicyEngine policyEngine;

public:
    explicit ContainerGovernanceEngine(SecurityPolicy policy)
        : policyEngine(policy) {}

    ScanReport scan(const ContainerImage& image) const {
        validateImage(image);

        vector<Finding> findings;

        auto vulnerabilities = vulnerabilityScanner.scan(image);
        auto secrets = secretScanner.scan(image);
        auto configurations = configurationScanner.scan(image);

        findings.insert(
            findings.end(),
            vulnerabilities.begin(),
            vulnerabilities.end()
        );

        findings.insert(
            findings.end(),
            secrets.begin(),
            secrets.end()
        );

        findings.insert(
            findings.end(),
            configurations.begin(),
            configurations.end()
        );

        DeploymentStatus status =
            policyEngine.evaluate(image, findings);

        return {
            image.reference(),
            findings,
            status
        };
    }
};

// ============================================================
// 9. RUNTIME SECURITY ENGINE
// ============================================================

enum class RuntimeEventType {
    PROCESS_EXECUTION,
    FILE_MODIFICATION,
    NETWORK_CONNECTION,
    PRIVILEGE_CHANGE,
    UNKNOWN
};

struct RuntimeEvent {
    string containerId;
    RuntimeEventType type;
    string process;
    string destination;
    bool privileged = false;
};

struct RuntimeDecision {
    bool allowed;
    Severity severity;
    string reason;
};

class RuntimeSecurityEngine {

    const set<string> blockedProcesses = {
        "nc", "ncat", "socat", "tcpdump", "chroot"
    };

    const set<string> protectedPaths = {
        "/etc/shadow",
        "/etc/passwd",
        "/root/.ssh/authorized_keys"
    };

public:
    RuntimeDecision evaluate(const RuntimeEvent& event) const {

        if (event.containerId.empty() || event.process.empty()) {
            throw invalid_argument(
                "Runtime event requires container ID and process."
            );
        }

        if (event.privileged) {
            return {
                false,
                Severity::CRITICAL,
                "Unexpected privileged execution."
            };
        }

        if (event.type == RuntimeEventType::PROCESS_EXECUTION) {
            size_t position = event.process.find_last_of('/');

            string executable =
                position == string::npos
                    ? event.process
                    : event.process.substr(position + 1);

            if (blockedProcesses.count(executable)) {
                return {
                    false,
                    Severity::HIGH,
                    "Restricted executable detected."
                };
            }
        }

        if (event.type == RuntimeEventType::FILE_MODIFICATION &&
            protectedPaths.count(event.destination)) {
            return {
                false,
                Severity::CRITICAL,
                "Protected system file modification."
            };
        }

        if (event.type == RuntimeEventType::UNKNOWN) {
            return {
                false,
                Severity::HIGH,
                "Unknown runtime behavior."
            };
        }

        return {
            true,
            Severity::INFO,
            "Runtime activity allowed."
        };
    }
};

// ============================================================
// 10. REMEDIATION WORKFLOW
// ============================================================

class RemediationTicket {

    static bool validTransition(
        ReviewStatus current,
        ReviewStatus next
    ) {
        switch (current) {
            case ReviewStatus::OPEN:
                return next == ReviewStatus::IN_PROGRESS ||
                       next == ReviewStatus::ACCEPTED_RISK;

            case ReviewStatus::IN_PROGRESS:
                return next == ReviewStatus::MITIGATED ||
                       next == ReviewStatus::RESOLVED ||
                       next == ReviewStatus::ACCEPTED_RISK;

            case ReviewStatus::MITIGATED:
                return next == ReviewStatus::RESOLVED ||
                       next == ReviewStatus::IN_PROGRESS;

            case ReviewStatus::RESOLVED:
                return next == ReviewStatus::OPEN;

            case ReviewStatus::ACCEPTED_RISK:
                return next == ReviewStatus::OPEN ||
                       next == ReviewStatus::IN_PROGRESS;
        }

        return false;
    }

    ReviewStatus status = ReviewStatus::OPEN;

public:
    string ticketId;
    string cve;
    string image;
    string owner;

    RemediationTicket(
        string id,
        string vulnerability,
        string imageReference,
        string assignedOwner
    ) : ticketId(move(id)),
        cve(move(vulnerability)),
        image(move(imageReference)),
        owner(move(assignedOwner)) {

        if (ticketId.empty() || cve.empty() ||
            image.empty() || owner.empty()) {
            throw invalid_argument(
                "Remediation ticket fields are mandatory."
            );
        }
    }

    void transition(ReviewStatus next) {
        if (!validTransition(status, next)) {
            throw logic_error(
                "Invalid remediation state transition."
            );
        }

        status = next;
    }

    ReviewStatus getStatus() const {
        return status;
    }
};

// ============================================================
// 11. SAMPLE IMAGE FACTORIES
// ============================================================

ContainerImage createUnsafeImage() {
    ContainerImage image;

    image.name = "inventory-service";
    image.tag = "latest";
    image.baseImage = "ubuntu:latest";

    image.packages = {
        {"openssl", "1.0.2"},
        {"curl", "7.50.0"},
        {"python", "3.12"}
    };

    image.vulnerabilities = {
        {
            "CVE-2025-10001",
            "openssl",
            "1.0.2",
            string("3.0.15"),
            Severity::CRITICAL,
            "Critical cryptographic weakness.",
            true
        },
        {
            "CVE-2025-10002",
            "curl",
            "7.50.0",
            string("8.10.0"),
            Severity::HIGH,
            "Network request vulnerability.",
            false
        }
    };

    image.exposedPorts = {22, 8080};

    image.environment = {
        {"DATABASE_PASSWORD", "production_password_123"}
    };

    image.user = "root";
    image.entrypoint = {"python", "app.py"};

    image.layers = 24;
    image.sizeMB = 850;

    image.signedImage = false;
    image.hasDigest = false;
    image.healthcheck = false;

    return image;
}

ContainerImage createSecureImage() {
    ContainerImage image;

    image.name = "inventory-service";
    image.tag = "2.1.0";
    image.baseImage = "python:3.12-slim";

    image.packages = {
        {"python", "3.12"},
        {"application", "2.1.0"}
    };

    image.environment = {
        {"APP_MODE", "production"},
        {"DATABASE_HOST", "database.internal"}
    };

    image.exposedPorts = {8080};

    image.user = "10001";
    image.entrypoint = {
        "python",
        "-m",
        "inventory_service"
    };

    image.layers = 7;
    image.sizeMB = 95;

    image.signedImage = true;
    image.hasDigest = true;
    image.healthcheck = true;

    return image;
}

// ============================================================
// 12. REPORTING
// ============================================================

void printReport(const ScanReport& report) {
    cout << "\n========================================\n";
    cout << "IMAGE: " << report.imageReference << "\n";
    cout << "STATUS: " << toString(report.status) << "\n";
    cout << "========================================\n";

    for (const auto& [severity, count] :
         report.severityCounts()) {
        cout << toString(severity) << ": " << count << "\n";
    }

    for (const Finding& finding : report.findings) {
        cout << "\n[" << toString(finding.severity) << "] "
             << toString(finding.type) << "\n";

        cout << "Resource: " << finding.resource << "\n";
        cout << "Issue: " << finding.description << "\n";
        cout << "Remediation: " << finding.remediation << "\n";
    }
}

// ============================================================
// 13. TESTS
// ============================================================

void runTests() {
    SecurityPolicy policy;

    ContainerGovernanceEngine engine(policy);

    ContainerImage unsafe = createUnsafeImage();
    ContainerImage secure = createSecureImage();

    ScanReport unsafeReport = engine.scan(unsafe);
    ScanReport secureReport = engine.scan(secure);

    if (unsafeReport.status != DeploymentStatus::BLOCKED) {
        throw runtime_error("Unsafe image was not blocked.");
    }

    if (secureReport.status != DeploymentStatus::APPROVED) {
        throw runtime_error("Secure image was not approved.");
    }

    RuntimeSecurityEngine runtime;

    RuntimeDecision allowed = runtime.evaluate({
        "container-101",
        RuntimeEventType::PROCESS_EXECUTION,
        "/usr/local/bin/python",
        "",
        false
    });

    RuntimeDecision blocked = runtime.evaluate({
        "container-101",
        RuntimeEventType::PROCESS_EXECUTION,
        "/usr/bin/nc",
        "",
        false
    });

    if (!allowed.allowed || blocked.allowed) {
        throw runtime_error("Runtime security test failed.");
    }

    RemediationTicket ticket(
        "SEC-1001",
        "CVE-2025-10001",
        "inventory-service:latest",
        "platform-team"
    );

    ticket.transition(ReviewStatus::IN_PROGRESS);

    if (ticket.getStatus() != ReviewStatus::IN_PROGRESS) {
        throw runtime_error("Remediation transition failed.");
    }

    bool rejected = false;

    try {
        ticket.transition(ReviewStatus::OPEN);
    } catch (const logic_error&) {
        rejected = true;
    }

    if (!rejected) {
        throw runtime_error(
            "Invalid remediation transition was accepted."
        );
    }

    bool invalidImageRejected = false;

    try {
        ContainerImage invalid = secure;
        invalid.sizeMB = -1;
        engine.scan(invalid);
    } catch (const invalid_argument&) {
        invalidImageRejected = true;
    }

    if (!invalidImageRejected) {
        throw runtime_error("Invalid image was accepted.");
    }

    cout << "All C++17 security tests passed.\n";
}

// ============================================================
// 14. MAIN
// ============================================================

int main() {
    try {
        runTests();

        SecurityPolicy policy;
        policy.maximumCritical = 0;
        policy.maximumHigh = 0;
        policy.maximumMedium = 3;

        ContainerGovernanceEngine engine(policy);

        vector<ContainerImage> images = {
            createUnsafeImage(),
            createSecureImage()
        };

        for (const ContainerImage& image : images) {
            ScanReport report = engine.scan(image);
            printReport(report);
        }

        RuntimeSecurityEngine runtime;

        vector<RuntimeEvent> events = {
            {
                "container-101",
                RuntimeEventType::PROCESS_EXECUTION,
                "/usr/local/bin/python",
                "",
                false
            },
            {
                "container-101",
                RuntimeEventType::FILE_MODIFICATION,
                "file-writer",
                "/etc/shadow",
                false
            },
            {
                "container-101",
                RuntimeEventType::PRIVILEGE_CHANGE,
                "privilege-escalation",
                "",
                true
            }
        };

        cout << "\nRUNTIME SECURITY EVENTS\n";

        for (const RuntimeEvent& event : events) {
            RuntimeDecision decision = runtime.evaluate(event);

            cout << (decision.allowed ? "ALLOW" : "BLOCK")
                 << " | "
                 << toString(decision.severity)
                 << " | "
                 << decision.reason
                 << "\n";
        }

    } catch (const exception& error) {
        cerr << "Security engine error: "
             << error.what() << "\n";

        return 1;
    }

    return 0;
}
