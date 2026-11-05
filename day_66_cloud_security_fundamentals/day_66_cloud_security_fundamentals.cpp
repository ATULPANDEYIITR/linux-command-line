#include <algorithm>
#include <iostream>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>
#include <numeric>
#include <iomanip>

/*
 * Cloud Security Fundamentals
 *
 * C++17 cloud infrastructure risk assessment engine.
 * Focus: service models, shared responsibility, security
 * configurations, compliance and risk prioritization.
 */

enum class ServiceModel {
    IaaS,
    PaaS,
    SaaS
};

enum class Owner {
    Customer,
    Provider,
    Shared
};

enum class Severity {
    Low = 1,
    Medium = 2,
    High = 3,
    Critical = 4
};

enum class Environment {
    Development,
    Testing,
    Staging,
    Production
};

enum class AssetStatus {
    Active,
    Quarantined,
    Retired
};

std::string toString(ServiceModel model) {
    switch (model) {
        case ServiceModel::IaaS: return "IaaS";
        case ServiceModel::PaaS: return "PaaS";
        case ServiceModel::SaaS: return "SaaS";
    }
    throw std::invalid_argument("Invalid service model");
}

std::string toString(Owner owner) {
    switch (owner) {
        case Owner::Customer: return "Customer";
        case Owner::Provider: return "Provider";
        case Owner::Shared: return "Shared";
    }
    throw std::invalid_argument("Invalid owner");
}

std::string toString(Severity severity) {
    switch (severity) {
        case Severity::Low: return "LOW";
        case Severity::Medium: return "MEDIUM";
        case Severity::High: return "HIGH";
        case Severity::Critical: return "CRITICAL";
    }
    throw std::invalid_argument("Invalid severity");
}

std::string toString(Environment environment) {
    switch (environment) {
        case Environment::Development: return "Development";
        case Environment::Testing: return "Testing";
        case Environment::Staging: return "Staging";
        case Environment::Production: return "Production";
    }
    throw std::invalid_argument("Invalid environment");
}

struct SecurityConfiguration {
    bool publicAccess = false;
    bool encryptionAtRest = false;
    bool encryptionInTransit = false;
    bool mfa = false;
    bool logging = false;
    bool backup = false;
    bool leastPrivilege = false;
    bool patching = false;
};

struct CloudAsset {
    std::string id;
    std::string name;
    ServiceModel model;
    Environment environment;
    SecurityConfiguration configuration;
    AssetStatus status = AssetStatus::Active;
    unsigned int version = 1;

    void validate() const {
        if (id.empty() || name.empty()) {
            throw std::invalid_argument(
                "Asset ID and name are mandatory"
            );
        }

        if (id.size() > 64 || name.size() > 150) {
            throw std::invalid_argument(
                "Asset identifier or name exceeds allowed length"
            );
        }
    }
};

struct ControlDefinition {
    std::string id;
    std::string name;
    Owner owner;
};

struct Finding {
    std::string assetId;
    std::string controlId;
    std::string description;
    Owner responsibility;
    Severity severity;
    bool compliant;
    std::string remediation;
};

struct Assessment {
    std::string assetId;
    std::vector<Finding> findings;

    int riskScore() const {
        return std::accumulate(
            findings.begin(),
            findings.end(),
            0,
            [](int total, const Finding& finding) {
                return total + (
                    finding.compliant
                        ? 0
                        : static_cast<int>(finding.severity)
                );
            }
        );
    }

    bool compliant() const {
        return std::all_of(
            findings.begin(),
            findings.end(),
            [](const Finding& finding) {
                return finding.compliant;
            }
        );
    }
};

class ResponsibilityModel {
private:
    std::map<std::string, ControlDefinition> controls;

public:
    ResponsibilityModel() {
        add("PHYSICAL", "Physical infrastructure", Owner::Provider);
        add("HYPERVISOR", "Hypervisor security", Owner::Provider);
        add("IDENTITY", "Identity and access management", Owner::Shared);
        add("NETWORK", "Network security", Owner::Shared);
        add("DATA", "Data protection", Owner::Shared);
        add("MONITORING", "Security monitoring", Owner::Shared);
        add("APPLICATION", "Application security", Owner::Customer);
        add("GUEST_OS", "Guest operating system", Owner::Customer);
    }

    void add(
        const std::string& id,
        const std::string& name,
        Owner owner
    ) {
        if (id.empty() || name.empty()) {
            throw std::invalid_argument("Invalid control definition");
        }

        auto inserted = controls.emplace(
            id,
            ControlDefinition{id, name, owner}
        );

        if (!inserted.second) {
            throw std::invalid_argument("Duplicate control ID");
        }
    }

    Owner getOwner(const std::string& id) const {
        auto it = controls.find(id);

        if (it == controls.end()) {
            throw std::out_of_range("Unknown control: " + id);
        }

        return it->second.owner;
    }

    void print() const {
        std::cout << "\nSHARED RESPONSIBILITY MODEL\n";

        for (const auto& entry : controls) {
            const auto& control = entry.second;

            std::cout
                << std::left
                << std::setw(15) << control.id
                << std::setw(12) << toString(control.owner)
                << control.name << '\n';
        }
    }
};

struct SecurityRule {
    std::string id;
    std::string description;
    Severity severity;
    Owner owner;
    std::string remediation;
    std::set<ServiceModel> applicableModels;
};

class CloudSecurityEngine {
private:
    std::vector<SecurityRule> rules;

    void addRule(
        const std::string& id,
        const std::string& description,
        Severity severity,
        Owner owner,
        const std::string& remediation,
        std::set<ServiceModel> models
    ) {
        rules.push_back({
            id,
            description,
            severity,
            owner,
            remediation,
            std::move(models)
        });
    }

    void initializeRules() {
        const std::set<ServiceModel> allModels = {
            ServiceModel::IaaS,
            ServiceModel::PaaS,
            ServiceModel::SaaS
        };

        addRule(
            "ENCRYPTION_AT_REST",
            "Storage encryption",
            Severity::High,
            Owner::Customer,
            "Enable encryption at rest.",
            allModels
        );

        addRule(
            "ENCRYPTION_IN_TRANSIT",
            "Transport encryption",
            Severity::High,
            Owner::Shared,
            "Enforce TLS for data in transit.",
            allModels
        );

        addRule(
            "MFA",
            "Multi-factor authentication",
            Severity::Critical,
            Owner::Customer,
            "Enforce MFA for user and privileged identities.",
            allModels
        );

        addRule(
            "LOGGING",
            "Security logging",
            Severity::High,
            Owner::Shared,
            "Enable centralized logging and alerting.",
            allModels
        );

        addRule(
            "BACKUP",
            "Backup protection",
            Severity::High,
            Owner::Shared,
            "Configure protected backups and test restoration.",
            allModels
        );

        addRule(
            "LEAST_PRIVILEGE",
            "Least privilege",
            Severity::High,
            Owner::Customer,
            "Reduce excessive identity permissions.",
            allModels
        );

        addRule(
            "PUBLIC_ACCESS",
            "Production public exposure",
            Severity::Critical,
            Owner::Customer,
            "Restrict unintended public access.",
            allModels
        );

        addRule(
            "GUEST_OS_PATCHING",
            "Guest operating system patching",
            Severity::High,
            Owner::Customer,
            "Patch and harden the guest operating system.",
            {ServiceModel::IaaS}
        );
    }

    static bool evaluateRule(
        const SecurityRule& rule,
        const CloudAsset& asset
    ) {
        const auto& config = asset.configuration;

        if (rule.id == "ENCRYPTION_AT_REST") {
            return config.encryptionAtRest;
        }

        if (rule.id == "ENCRYPTION_IN_TRANSIT") {
            return config.encryptionInTransit;
        }

        if (rule.id == "MFA") {
            return config.mfa;
        }

        if (rule.id == "LOGGING") {
            return config.logging;
        }

        if (rule.id == "BACKUP") {
            return config.backup;
        }

        if (rule.id == "LEAST_PRIVILEGE") {
            return config.leastPrivilege;
        }

        if (rule.id == "PUBLIC_ACCESS") {
            return !(
                asset.environment == Environment::Production &&
                config.publicAccess
            );
        }

        if (rule.id == "GUEST_OS_PATCHING") {
            return config.patching;
        }

        throw std::logic_error("Unknown evaluation rule");
    }

public:
    CloudSecurityEngine() {
        initializeRules();
    }

    Assessment assess(const CloudAsset& asset) const {
        asset.validate();

        if (asset.status != AssetStatus::Active) {
            throw std::logic_error(
                "Only active assets can be assessed"
            );
        }

        Assessment assessment;
        assessment.assetId = asset.id;

        for (const auto& rule : rules) {
            if (rule.applicableModels.count(asset.model) == 0) {
                continue;
            }

            bool passed = evaluateRule(rule, asset);

            assessment.findings.push_back({
                asset.id,
                rule.id,
                rule.description,
                rule.owner,
                rule.severity,
                passed,
                passed ? "" : rule.remediation
            });
        }

        return assessment;
    }

    const std::vector<SecurityRule>& getRules() const {
        return rules;
    }
};

class CloudInventory {
private:
    std::map<std::string, CloudAsset> assets;

public:
    void registerAsset(const CloudAsset& asset) {
        asset.validate();

        if (assets.find(asset.id) != assets.end()) {
            throw std::invalid_argument(
                "Duplicate asset: " + asset.id
            );
        }

        assets.emplace(asset.id, asset);
    }

    const CloudAsset& get(const std::string& id) const {
        auto it = assets.find(id);

        if (it == assets.end()) {
            throw std::out_of_range("Asset not found");
        }

        return it->second;
    }

    const std::map<std::string, CloudAsset>& all() const {
        return assets;
    }
};

class SecurityReporting {
public:
    static void print(const Assessment& assessment) {
        std::cout
            << "\nAsset: " << assessment.assetId
            << "\nRisk score: " << assessment.riskScore()
            << "\nStatus: "
            << (assessment.compliant() ? "COMPLIANT" : "NON-COMPLIANT")
            << '\n';

        for (const auto& finding : assessment.findings) {
            if (!finding.compliant) {
                std::cout
                    << "  [" << toString(finding.severity) << "] "
                    << finding.controlId
                    << " | Owner: "
                    << toString(finding.responsibility)
                    << "\n  Remediation: "
                    << finding.remediation << '\n';
            }
        }
    }

    static void summary(const std::vector<Assessment>& assessments) {
        int compliant = 0;
        int nonCompliant = 0;
        int totalFindings = 0;

        for (const auto& assessment : assessments) {
            if (assessment.compliant()) {
                compliant++;
            } else {
                nonCompliant++;
            }

            for (const auto& finding : assessment.findings) {
                if (!finding.compliant) {
                    totalFindings++;
                }
            }
        }

        std::cout << "\nSECURITY SUMMARY\n";
        std::cout << "Total assets: " << assessments.size() << '\n';
        std::cout << "Compliant: " << compliant << '\n';
        std::cout << "Non-compliant: " << nonCompliant << '\n';
        std::cout << "Open findings: " << totalFindings << '\n';
    }
};

void runTests() {
    ResponsibilityModel responsibility;

    if (responsibility.getOwner("PHYSICAL") != Owner::Provider) {
        throw std::runtime_error("Physical security test failed");
    }

    if (responsibility.getOwner("DATA") != Owner::Shared) {
        throw std::runtime_error("Data responsibility test failed");
    }

    CloudSecurityEngine engine;

    CloudAsset secure{
        "TEST-001",
        "Secure server",
        ServiceModel::IaaS,
        Environment::Production,
        {
            false, true, true, true,
            true, true, true, true
        }
    };

    Assessment secureAssessment = engine.assess(secure);

    if (!secureAssessment.compliant()) {
        throw std::runtime_error("Secure asset test failed");
    }

    CloudAsset exposed{
        "TEST-002",
        "Exposed storage",
        ServiceModel::SaaS,
        Environment::Production,
        {
            true, false, false, false,
            false, false, false, false
        }
    };

    Assessment exposedAssessment = engine.assess(exposed);

    if (exposedAssessment.compliant()) {
        throw std::runtime_error("Exposure test failed");
    }

    if (exposedAssessment.riskScore() <= 0) {
        throw std::runtime_error("Risk calculation test failed");
    }

    try {
        CloudAsset invalid{
            "",
            "Invalid",
            ServiceModel::IaaS,
            Environment::Production,
            {}
        };

        engine.assess(invalid);
        throw std::runtime_error("Invalid asset accepted");
    } catch (const std::invalid_argument&) {
        // Expected validation failure.
    }

    std::cout << "\nAll C++17 tests passed.\n";
}

int main() {
    try {
        ResponsibilityModel responsibility;
        responsibility.print();

        CloudInventory inventory;

        inventory.registerAsset({
            "AWS-EC2-001",
            "Production API server",
            ServiceModel::IaaS,
            Environment::Production,
            {
                false, true, true, true,
                true, true, true, true
            }
        });

        inventory.registerAsset({
            "AZURE-APP-002",
            "Managed application",
            ServiceModel::PaaS,
            Environment::Production,
            {
                false, true, true, false,
                true, true, false, false
            }
        });

        inventory.registerAsset({
            "SAAS-003",
            "Enterprise document service",
            ServiceModel::SaaS,
            Environment::Production,
            {
                true, true, true, false,
                false, false, false, false
            }
        });

        CloudSecurityEngine engine;
        std::vector<Assessment> assessments;

        std::cout << "\nCLOUD SECURITY ASSESSMENTS\n";

        for (const auto& entry : inventory.all()) {
            try {
                Assessment result = engine.assess(entry.second);

                SecurityReporting::print(result);
                assessments.push_back(std::move(result));
            } catch (const std::exception& error) {
                std::cerr
                    << "Assessment failed for "
                    << entry.first << ": "
                    << error.what() << '\n';
            }
        }

        SecurityReporting::summary(assessments);

        runTests();

    } catch (const std::exception& error) {
        std::cerr << "Fatal error: " << error.what() << '\n';
        return 1;
    }

    return 0;
}
```

```java
import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;

/*
 * Cloud Security Fundamentals
 *
 * Java 17 enterprise cloud governance application.
 *
 * Models:
 * - Shared responsibility
 * - IaaS, PaaS and SaaS
 * - Security control ownership
 * - Policy evaluation
 * - Compliance findings
 * - Risk scoring
 * - Asset lifecycle
 * - Enterprise security reporting
 */

public class Main {

    enum ServiceModel {
        IAAS, PAAS, SAAS
    }

    enum Responsibility {
        CUSTOMER, PROVIDER, SHARED
    }

    enum Severity {
        LOW(1),
        MEDIUM(2),
        HIGH(3),
        CRITICAL(4);

        private final int weight;

        Severity(int weight) {
            this.weight = weight;
        }

        public int weight() {
            return weight;
        }
    }

    enum Environment {
        DEVELOPMENT, TESTING, STAGING, PRODUCTION
    }

    enum AssetStatus {
        ACTIVE, QUARANTINED, RETIRED
    }

    enum ComplianceStatus {
        COMPLIANT, NON_COMPLIANT
    }

    static class SecurityException extends RuntimeException {
        public SecurityException(String message) {
            super(message);
        }
    }

    record ControlDefinition(
        String id,
        String name,
        Responsibility responsibility
    ) {
        ControlDefinition {
            Objects.requireNonNull(id);
            Objects.requireNonNull(name);
            Objects.requireNonNull(responsibility);

            if (id.isBlank() || name.isBlank()) {
                throw new IllegalArgumentException(
                    "Control ID and name are required"
                );
            }
        }
    }

    record SecurityConfiguration(
        boolean publicAccess,
        boolean encryptionAtRest,
        boolean encryptionInTransit,
        boolean mfa,
        boolean logging,
        boolean backup,
        boolean leastPrivilege,
        boolean patching
    ) {}

    record SecurityRule(
        String id,
        String description,
        Severity severity,
        Responsibility responsibility,
        Set<ServiceModel> applicableModels,
        String remediation
    ) {
        SecurityRule {
            Objects.requireNonNull(id);
            Objects.requireNonNull(description);
            Objects.requireNonNull(severity);
            Objects.requireNonNull(responsibility);
            Objects.requireNonNull(remediation);

            applicableModels = Collections.unmodifiableSet(
                EnumSet.copyOf(applicableModels)
            );
        }

        boolean appliesTo(ServiceModel model) {
            return applicableModels.contains(model);
        }
    }

    static class CloudAsset {
        private final String id;
        private final String name;
        private final ServiceModel serviceModel;
        private final Environment environment;

        private SecurityConfiguration configuration;
        private AssetStatus status;
        private long version;

        CloudAsset(
            String id,
            String name,
            ServiceModel serviceModel,
            Environment environment,
            SecurityConfiguration configuration
        ) {
            if (id == null || id.isBlank() ||
                name == null || name.isBlank()) {
                throw new IllegalArgumentException(
                    "Asset ID and name are mandatory"
                );
            }

            this.id = id;
            this.name = name;
            this.serviceModel = Objects.requireNonNull(serviceModel);
            this.environment = Objects.requireNonNull(environment);
            this.configuration = Objects.requireNonNull(configuration);
            this.status = AssetStatus.ACTIVE;
            this.version = 1;
        }

        public String id() {
            return id;
        }

        public String name() {
            return name;
        }

        public ServiceModel serviceModel() {
            return serviceModel;
        }

        public Environment environment() {
            return environment;
        }

        public SecurityConfiguration configuration() {
            return configuration;
        }

        public AssetStatus status() {
            return status;
        }

        public long version() {
            return version;
        }

        public void updateConfiguration(
            SecurityConfiguration newConfiguration
        ) {
            if (status != AssetStatus.ACTIVE) {
                throw new SecurityException(
                    "Only active assets can be modified"
                );
            }

            configuration = Objects.requireNonNull(newConfiguration);
            version++;
        }

        public void quarantine() {
            if (status != AssetStatus.ACTIVE) {
                throw new SecurityException(
                    "Asset cannot be quarantined from its current state"
                );
            }

            status = AssetStatus.QUARANTINED;
        }

        public void retire() {
            if (status == AssetStatus.RETIRED) {
                throw new SecurityException("Asset already retired");
            }

            status = AssetStatus.RETIRED;
        }
    }

    record Finding(
        String assetId,
        String ruleId,
        String description,
        Responsibility responsibility,
        Severity severity,
        ComplianceStatus status,
        String remediation
    ) {}

    record Assessment(
        String assessmentId,
        String assetId,
        long assetVersion,
        Instant evaluatedAt,
        List<Finding> findings
    ) {
        Assessment {
            findings = List.copyOf(findings);
        }

        int riskScore() {
            return findings.stream()
                .filter(f -> f.status() == ComplianceStatus.NON_COMPLIANT)
                .mapToInt(f -> f.severity().weight())
                .sum();
        }

        boolean compliant() {
            return findings.stream()
                .allMatch(f -> f.status() == ComplianceStatus.COMPLIANT);
        }

        long countBySeverity(Severity severity) {
            return findings.stream()
                .filter(f ->
                    f.status() == ComplianceStatus.NON_COMPLIANT &&
                    f.severity() == severity
                )
                .count();
        }
    }

    static class ResponsibilityRegistry {
        private final Map<String, ControlDefinition> controls =
            new LinkedHashMap<>();

        ResponsibilityRegistry() {
            register(new ControlDefinition(
                "PHYSICAL",
                "Physical infrastructure security",
                Responsibility.PROVIDER
            ));

            register(new ControlDefinition(
                "HYPERVISOR",
                "Virtualization infrastructure",
                Responsibility.PROVIDER
            ));

            register(new ControlDefinition(
                "IDENTITY",
                "Identity and access management",
                Responsibility.SHARED
            ));

            register(new ControlDefinition(
                "NETWORK",
                "Network security",
                Responsibility.SHARED
            ));

            register(new ControlDefinition(
                "DATA",
                "Data protection",
                Responsibility.SHARED
            ));

            register(new ControlDefinition(
                "MONITORING",
                "Security monitoring",
                Responsibility.SHARED
            ));

            register(new ControlDefinition(
                "APPLICATION",
                "Application security",
                Responsibility.CUSTOMER
            ));

            register(new ControlDefinition(
                "GUEST_OS",
                "Guest operating system",
                Responsibility.CUSTOMER
            ));
        }

        void register(ControlDefinition control) {
            if (controls.putIfAbsent(control.id(), control) != null) {
                throw new SecurityException(
                    "Duplicate control: " + control.id()
                );
            }
        }

        ControlDefinition get(String id) {
            ControlDefinition control = controls.get(id);

            if (control == null) {
                throw new SecurityException(
                    "Unknown control: " + id
                );
            }

            return control;
        }

        List<ControlDefinition> all() {
            return List.copyOf(controls.values());
        }
    }

    static class SecurityPolicy {
        private final List<SecurityRule> rules;

        SecurityPolicy() {
            List<SecurityRule> configuredRules = new ArrayList<>();

            Set<ServiceModel> allModels =
                EnumSet.allOf(ServiceModel.class);

            configuredRules.add(new SecurityRule(
                "ENCRYPTION_AT_REST",
                "Storage encryption",
                Severity.HIGH,
                Responsibility.CUSTOMER,
                allModels,
                "Enable encryption at rest."
            ));

            configuredRules.add(new SecurityRule(
                "ENCRYPTION_IN_TRANSIT",
                "Transport encryption",
                Severity.HIGH,
                Responsibility.SHARED,
                allModels,
                "Enforce TLS for data in transit."
            ));

            configuredRules.add(new SecurityRule(
                "MFA",
                "Multi-factor authentication",
                Severity.CRITICAL,
                Responsibility.CUSTOMER,
                allModels,
                "Enable MFA for all relevant identities."
            ));

            configuredRules.add(new SecurityRule(
                "LOGGING",
                "Security event logging",
                Severity.HIGH,
                Responsibility.SHARED,
                allModels,
                "Enable centralized security logging."
            ));

            configuredRules.add(new SecurityRule(
                "BACKUP",
                "Protected backup",
                Severity.HIGH,
                Responsibility.SHARED,
                allModels,
                "Configure protected backups and recovery testing."
            ));

            configuredRules.add(new SecurityRule(
                "LEAST_PRIVILEGE",
                "Least privilege",
                Severity.HIGH,
                Responsibility.CUSTOMER,
                allModels,
                "Remove excessive permissions."
            ));

            configuredRules.add(new SecurityRule(
                "PUBLIC_ACCESS",
                "Production public exposure",
                Severity.CRITICAL,
                Responsibility.CUSTOMER,
                allModels,
                "Restrict unintended public access."
            ));

            configuredRules.add(new SecurityRule(
                "GUEST_OS_PATCHING",
                "Guest operating system patching",
                Severity.HIGH,
                Responsibility.CUSTOMER,
                EnumSet.of(ServiceModel.IAAS),
                "Apply and verify operating system patches."
            ));

            rules = List.copyOf(configuredRules);
        }

        List<SecurityRule> rules() {
            return rules;
        }
    }

    static class SecurityAssessmentService {
        private final SecurityPolicy policy;

        SecurityAssessmentService(SecurityPolicy policy) {
            this.policy = Objects.requireNonNull(policy);
        }

        Assessment evaluate(CloudAsset asset) {
            Objects.requireNonNull(asset);

            if (asset.status() != AssetStatus.ACTIVE) {
                throw new SecurityException(
                    "Cannot assess inactive assets"
                );
            }

            long initialVersion = asset.version();

            List<Finding> findings = policy.rules().stream()
                .filter(rule -> rule.appliesTo(asset.serviceModel()))
                .map(rule -> {
                    boolean passed = evaluateRule(rule, asset);

                    return new Finding(
                        asset.id(),
                        rule.id(),
                        rule.description(),
                        rule.responsibility(),
                        rule.severity(),
                        passed
                            ? ComplianceStatus.COMPLIANT
                            : ComplianceStatus.NON_COMPLIANT,
                        passed ? "" : rule.remediation()
                    );
                })
                .collect(Collectors.toList());

            if (asset.version() != initialVersion) {
                throw new SecurityException(
                    "Asset changed during assessment"
                );
            }

            return new Assessment(
                UUID.randomUUID().toString(),
                asset.id(),
                initialVersion,
                Instant.now(),
                findings
            );
        }

        private boolean evaluateRule(
            SecurityRule rule,
            CloudAsset asset
        ) {
            SecurityConfiguration c = asset.configuration();

            return switch (rule.id()) {
                case "ENCRYPTION_AT_REST" ->
                    c.encryptionAtRest();

                case "ENCRYPTION_IN_TRANSIT" ->
                    c.encryptionInTransit();

                case "MFA" ->
                    c.mfa();

                case "LOGGING" ->
                    c.logging();

                case "BACKUP" ->
                    c.backup();

                case "LEAST_PRIVILEGE" ->
                    c.leastPrivilege();

                case "PUBLIC_ACCESS" ->
                    !(asset.environment() == Environment.PRODUCTION
                        && c.publicAccess());

                case "GUEST_OS_PATCHING" ->
                    c.patching();

                default ->
                    throw new SecurityException(
                        "Unknown rule: " + rule.id()
                    );
            };
        }
    }

    static class CloudInventory {
        private final Map<String, CloudAsset> assets =
            new LinkedHashMap<>();

        void register(CloudAsset asset) {
            Objects.requireNonNull(asset);

            if (assets.putIfAbsent(asset.id(), asset) != null) {
                throw new SecurityException(
                    "Asset already registered: " + asset.id()
                );
            }
        }

        CloudAsset get(String id) {
            CloudAsset asset = assets.get(id);

            if (asset == null) {
                throw new SecurityException(
                    "Asset not found: " + id
                );
            }

            return asset;
        }

        List<CloudAsset> all() {
            return List.copyOf(assets.values());
        }
    }

    static class SecurityReportingService {
        static void print(Assessment assessment) {
            System.out.println(
                "\nAsset: " + assessment.assetId()
            );

            System.out.println(
                "Risk score: " + assessment.riskScore()
            );

            System.out.println(
                "Status: " +
                (assessment.compliant()
                    ? "COMPLIANT"
                    : "NON-COMPLIANT")
            );

            assessment.findings().stream()
                .filter(f ->
                    f.status() == ComplianceStatus.NON_COMPLIANT
                )
                .forEach(f -> System.out.println(
                    "  [" + f.severity() + "] " +
                    f.ruleId() + " | " +
                    f.responsibility() + " | " +
                    f.remediation()
                ));
        }

        static void printSummary(List<Assessment> assessments) {
            long compliant = assessments.stream()
                .filter(Assessment::compliant)
                .count();

            long nonCompliant = assessments.size() - compliant;

            int totalFindings = assessments.stream()
                .mapToInt(a -> (int) a.findings().stream()
                    .filter(f ->
                        f.status() == ComplianceStatus.NON_COMPLIANT
                    )
                    .count())
                .sum();

            System.out.println("\nENTERPRISE SECURITY REPORT");
            System.out.println("Total assets: " + assessments.size());
            System.out.println("Compliant: " + compliant);
            System.out.println("Non-compliant: " + nonCompliant);
            System.out.println("Open findings: " + totalFindings);

            for (Severity severity : Severity.values()) {
                long count = assessments.stream()
                    .mapToLong(a -> a.countBySeverity(severity))
                    .sum();

                System.out.println(
                    severity + " findings: " + count
                );
            }
        }
    }

    static void runTests() {
        ResponsibilityRegistry registry =
            new ResponsibilityRegistry();

        if (registry.get("PHYSICAL").responsibility()
            != Responsibility.PROVIDER) {
            throw new AssertionError("Physical responsibility test failed");
        }

        if (registry.get("DATA").responsibility()
            != Responsibility.SHARED) {
            throw new AssertionError("Data responsibility test failed");
        }

        SecurityAssessmentService service =
            new SecurityAssessmentService(new SecurityPolicy());

        CloudAsset secure = new CloudAsset(
            "TEST-001",
            "Secure server",
            ServiceModel.IAAS,
            Environment.PRODUCTION,
            new SecurityConfiguration(
                false, true, true, true,
                true, true, true, true
            )
        );

        Assessment secureAssessment = service.evaluate(secure);

        if (!secureAssessment.compliant()) {
            throw new AssertionError("Secure asset test failed");
        }

        CloudAsset exposed = new CloudAsset(
            "TEST-002",
            "Public storage",
            ServiceModel.SAAS,
            Environment.PRODUCTION,
            new SecurityConfiguration(
                true, false, false, false,
                false, false, false, false
            )
        );

        Assessment exposedAssessment = service.evaluate(exposed);

        if (exposedAssessment.compliant() ||
            exposedAssessment.riskScore() <= 0) {
            throw new AssertionError("Exposure test failed");
        }

        secure.quarantine();

        try {
            service.evaluate(secure);
            throw new AssertionError(
                "Quarantined asset should not be assessed"
            );
        } catch (SecurityException expected) {
            // Expected lifecycle restriction.
        }

        System.out.println("\nAll Java 17 tests passed.");
    }

    public static void main(String[] args) {
        ResponsibilityRegistry registry =
            new ResponsibilityRegistry();

        System.out.println("SHARED RESPONSIBILITY MODEL");

        for (ControlDefinition control : registry.all()) {
            System.out.printf(
                "%-15s %-12s %s%n",
                control.id(),
                control.responsibility(),
                control.name()
            );
        }

        CloudInventory inventory = new CloudInventory();

        inventory.register(new CloudAsset(
            "AWS-EC2-001",
            "Production API server",
            ServiceModel.IAAS,
            Environment.PRODUCTION,
            new SecurityConfiguration(
                false, true, true, true,
                true, true, true, true
            )
        ));

        inventory.register(new CloudAsset(
            "AZURE-APP-002",
            "Managed application",
            ServiceModel.PAAS,
            Environment.PRODUCTION,
            new SecurityConfiguration(
                false, true, true, false,
                true, true, false, false
            )
        ));

        inventory.register(new CloudAsset(
            "SAAS-003",
            "Enterprise document service",
            ServiceModel.SAAS,
            Environment.PRODUCTION,
            new SecurityConfiguration(
                true, true, true, false,
                false, false, false, false
            )
        ));

        SecurityAssessmentService service =
            new SecurityAssessmentService(new SecurityPolicy());

        List<Assessment> assessments = new ArrayList<>();

        System.out.println("\nCLOUD SECURITY ASSESSMENTS");

        for (CloudAsset asset : inventory.all()) {
            try {
                Assessment assessment = service.evaluate(asset);
                assessments.add(assessment);
                SecurityReportingService.print(assessment);

            } catch (SecurityException exception) {
                System.err.println(
                    "Assessment failed: " + exception.getMessage()
                );
            }
        }

        SecurityReportingService.printSummary(assessments);

        runTests();
    }
}
```

```sql
/*
    CLOUD SECURITY FUNDAMENTALS
    PostgreSQL 14+

    Enterprise cloud asset security governance database.

    Models:
      1. Cloud providers and service models
      2. Shared responsibility assignments
      3. Cloud assets and configuration
      4. Security controls and policies
      5. Compliance assessments
      6. Security findings
      7. Risk scoring and remediation
      8. Asset lifecycle management

    The script is designed to run as a single PostgreSQL script.
*/

BEGIN;

CREATE SCHEMA IF NOT EXISTS cloud_security;

SET search_path TO cloud_security, public;

-- ============================================================
-- 1. ENUM TYPES
-- ============================================================

CREATE TYPE service_model AS ENUM (
    'IaaS',
    'PaaS',
    'SaaS'
);

CREATE TYPE responsibility_owner AS ENUM (
    'CUSTOMER',
    'PROVIDER',
    'SHARED'
);

CREATE TYPE environment_type AS ENUM (
    'DEVELOPMENT',
    'TESTING',
    'STAGING',
    'PRODUCTION'
);

CREATE TYPE severity_level AS ENUM (
    'LOW',
    'MEDIUM',
    'HIGH',
    'CRITICAL'
);

CREATE TYPE asset_state AS ENUM (
    'ACTIVE',
    'QUARANTINED',
    'RETIRED'
);

CREATE TYPE finding_state AS ENUM (
    'OPEN',
    'IN_PROGRESS',
    'RESOLVED',
    'ACCEPTED_RISK'
);

CREATE TYPE assessment_state AS ENUM (
    'RUNNING',
    'COMPLETED',
    'FAILED'
);

-- ============================================================
-- 2. ORGANIZATIONAL AND CLOUD PROVIDER DATA
-- ============================================================

CREATE TABLE organizations (
    organization_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    organization_name VARCHAR(150) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE cloud_providers (
    provider_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    provider_name VARCHAR(100) NOT NULL UNIQUE,
    provider_status BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE cloud_services (
    service_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    provider_id BIGINT NOT NULL
        REFERENCES cloud_providers(provider_id),

    service_name VARCHAR(150) NOT NULL,

    model service_model NOT NULL,

    description TEXT,

    UNIQUE(provider_id, service_name)
);

-- ============================================================
-- 3. SECURITY RESPONSIBILITY MODEL
-- ============================================================

CREATE TABLE security_domains (
    domain_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    domain_code VARCHAR(50) NOT NULL UNIQUE,
    domain_name VARCHAR(120) NOT NULL
);

CREATE TABLE security_controls (
    control_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    control_code VARCHAR(60) NOT NULL UNIQUE,

    domain_id BIGINT NOT NULL
        REFERENCES security_domains(domain_id),

    control_name VARCHAR(150) NOT NULL,

    description TEXT NOT NULL,

    severity severity_level NOT NULL,

    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE responsibility_assignments (
    assignment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    service_model service_model NOT NULL,

    control_id BIGINT NOT NULL
        REFERENCES security_controls(control_id),

    responsibility responsibility_owner NOT NULL,

    responsibility_description TEXT NOT NULL,

    UNIQUE(service_model, control_id)
);

-- ============================================================
-- 4. CLOUD ASSET INVENTORY
-- ============================================================

CREATE TABLE cloud_assets (
    asset_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    organization_id BIGINT NOT NULL
        REFERENCES organizations(organization_id),

    service_id BIGINT NOT NULL
        REFERENCES cloud_services(service_id),

    asset_code VARCHAR(80) NOT NULL UNIQUE,

    asset_name VARCHAR(150) NOT NULL,

    environment environment_type NOT NULL,

    region VARCHAR(100) NOT NULL,

    data_classification VARCHAR(30) NOT NULL
        CHECK (
            data_classification IN (
                'PUBLIC',
                'INTERNAL',
                'CONFIDENTIAL',
                'RESTRICTED'
            )
        ),

    public_access BOOLEAN NOT NULL DEFAULT FALSE,

    encryption_at_rest BOOLEAN NOT NULL DEFAULT FALSE,

    encryption_in_transit BOOLEAN NOT NULL DEFAULT FALSE,

    mfa_enabled BOOLEAN NOT NULL DEFAULT FALSE,

    logging_enabled BOOLEAN NOT NULL DEFAULT FALSE,

    backup_enabled BOOLEAN NOT NULL DEFAULT FALSE,

    least_privilege_enabled BOOLEAN NOT NULL DEFAULT FALSE,

    patching_enabled BOOLEAN NOT NULL DEFAULT FALSE,

    asset_status asset_state NOT NULL DEFAULT 'ACTIVE',

    version_number INTEGER NOT NULL DEFAULT 1
        CHECK (version_number > 0),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_assets_organization
    ON cloud_assets(organization_id);

CREATE INDEX idx_assets_service
    ON cloud_assets(service_id);

CREATE INDEX idx_assets_environment
    ON cloud_assets(environment);

CREATE INDEX idx_assets_active_environment
    ON cloud_assets(environment, updated_at)
    WHERE asset_status = 'ACTIVE';

CREATE INDEX idx_assets_public_production
    ON cloud_assets(asset_id)
    WHERE public_access = TRUE
      AND environment = 'PRODUCTION'
      AND asset_status = 'ACTIVE';

-- ============================================================
-- 5. SECURITY POLICY MANAGEMENT
-- ============================================================

CREATE TABLE security_policies (
    policy_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    policy_name VARCHAR(150) NOT NULL UNIQUE,

    policy_version VARCHAR(30) NOT NULL,

    description TEXT,

    effective_from DATE NOT NULL,

    effective_until DATE,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    CHECK (
        effective_until IS NULL
        OR effective_until >= effective_from
    )
);

CREATE TABLE policy_rules (
    rule_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    policy_id BIGINT NOT NULL
        REFERENCES security_policies(policy_id),

    control_id BIGINT NOT NULL
        REFERENCES security_controls(control_id),

    required BOOLEAN NOT NULL DEFAULT TRUE,

    applies_to service_model[] NOT NULL,

    remediation_guidance TEXT NOT NULL,

    UNIQUE(policy_id, control_id),

    CHECK (CARDINALITY(applies_to) > 0)
);

CREATE INDEX idx_policy_rules_policy
    ON policy_rules(policy_id);

-- ============================================================
-- 6. SECURITY ASSESSMENTS
-- ============================================================

CREATE TABLE security_assessments (
    assessment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    asset_id BIGINT NOT NULL
        REFERENCES cloud_assets(asset_id),

    policy_id BIGINT NOT NULL
        REFERENCES security_policies(policy_id),

    assessment_state assessment_state NOT NULL DEFAULT 'RUNNING',

    assessed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    completed_at TIMESTAMPTZ,

    assessed_asset_version INTEGER NOT NULL,

    risk_score INTEGER NOT NULL DEFAULT 0
        CHECK (risk_score >= 0),

    compliant BOOLEAN,

    assessment_notes TEXT,

    CHECK (
        completed_at IS NULL
        OR completed_at >= assessed_at
    )
);

CREATE INDEX idx_assessments_asset_date
    ON security_assessments(asset_id, assessed_at DESC);

CREATE INDEX idx_assessments_state
    ON security_assessments(assessment_state);

CREATE INDEX idx_assessments_noncompliant
    ON security_assessments(assessed_at DESC)
    WHERE compliant = FALSE;

CREATE TABLE security_findings (
    finding_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    assessment_id BIGINT NOT NULL
        REFERENCES security_assessments(assessment_id),

    control_id BIGINT NOT NULL
        REFERENCES security_controls(control_id),

    responsibility responsibility_owner NOT NULL,

    severity severity_level NOT NULL,

    is_compliant BOOLEAN NOT NULL,

    finding_status finding_state NOT NULL DEFAULT 'OPEN',

    evidence TEXT,

    remediation TEXT NOT NULL,

    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    resolved_at TIMESTAMPTZ,

    UNIQUE(assessment_id, control_id),

    CHECK (
        resolved_at IS NULL
        OR resolved_at >= detected_at
    ),

    CHECK (
        finding_status <> 'RESOLVED'
        OR is_compliant = TRUE
    )
);

CREATE INDEX idx_findings_open_severity
    ON security_findings(severity, detected_at DESC)
    WHERE finding_status = 'OPEN';

CREATE INDEX idx_findings_assessment
    ON security_findings(assessment_id);

-- ============================================================
-- 7. SECURITY AUDIT HISTORY
-- ============================================================

CREATE TABLE security_audit_log (
    log_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    asset_id BIGINT
        REFERENCES cloud_assets(asset_id),

    action VARCHAR(80) NOT NULL,

    old_state JSONB,

    new_state JSONB,

    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    database_user TEXT NOT NULL DEFAULT CURRENT_USER
);

-- ============================================================
-- 8. ASSET CHANGE TRIGGER
-- ============================================================

CREATE OR REPLACE FUNCTION record_asset_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN

        IF NEW.organization_id <> OLD.organization_id
           OR NEW.service_id <> OLD.service_id
           OR NEW.asset_code <> OLD.asset_code THEN

            RAISE EXCEPTION
                'Organization, service and asset code are immutable';
        END IF;

        IF OLD.asset_status = 'RETIRED' THEN
            RAISE EXCEPTION 'Retired assets cannot be modified';
        END IF;

        NEW.version_number := OLD.version_number + 1;
        NEW.updated_at := NOW();

        INSERT INTO security_audit_log (
            asset_id,
            action,
            old_state,
            new_state
        )
        VALUES (
            OLD.asset_id,
            'ASSET_UPDATED',
            TO_JSONB(OLD),
            TO_JSONB(NEW)
        );

        RETURN NEW;
    END IF;

    INSERT INTO security_audit_log (
        asset_id,
        action,
        new_state
    )
    VALUES (
        NEW.asset_id,
        'ASSET_CREATED',
        TO_JSONB(NEW)
    );

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_asset_audit
BEFORE INSERT OR UPDATE ON cloud_assets
FOR EACH ROW
EXECUTE FUNCTION record_asset_change();

-- ============================================================
-- 9. FINDING VALIDATION TRIGGER
-- ============================================================

CREATE OR REPLACE FUNCTION validate_finding()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    current_state assessment_state;
BEGIN
    SELECT assessment_state
    INTO current_state
    FROM security_assessments
    WHERE assessment_id = NEW.assessment_id;

    IF current_state IS DISTINCT FROM 'RUNNING' THEN
        RAISE EXCEPTION
            'Findings can only be added to running assessments';
    END IF;

    IF NEW.finding_status = 'RESOLVED'
       AND NEW.is_compliant = FALSE THEN
        RAISE EXCEPTION
            'A non-compliant finding cannot be marked resolved';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_finding
BEFORE INSERT OR UPDATE ON security_findings
FOR EACH ROW
EXECUTE FUNCTION validate_finding();

-- ============================================================
-- 10. ASSESSMENT COMPLETION FUNCTION
-- ============================================================

CREATE OR REPLACE FUNCTION complete_security_assessment(
    p_assessment_id BIGINT
)
RETURNS TABLE (
    result_risk_score INTEGER,
    result_compliant BOOLEAN,
    result_findings BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_risk_score INTEGER;
    v_compliant BOOLEAN;
    v_total BIGINT;
BEGIN
    -- Lock the assessment while finalizing it.
    PERFORM 1
    FROM security_assessments
    WHERE assessment_id = p_assessment_id
      AND assessment_state = 'RUNNING'
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Assessment does not exist or is not running';
    END IF;

    SELECT
        COALESCE(
            SUM(
                CASE severity
                    WHEN 'CRITICAL' THEN 4
                    WHEN 'HIGH' THEN 3
                    WHEN 'MEDIUM' THEN 2
                    WHEN 'LOW' THEN 1
                END
            ) FILTER (
                WHERE NOT is_compliant
                  AND finding_status <> 'ACCEPTED_RISK'
            ),
            0
        )::INTEGER,

        COUNT(*) FILTER (
            WHERE NOT is_compliant
              AND finding_status <> 'ACCEPTED_RISK'
        ),

        COUNT(*)

    INTO v_risk_score, v_total, result_findings

    FROM security_findings
    WHERE assessment_id = p_assessment_id;

    v_compliant := v_total = 0;

    UPDATE security_assessments
    SET
        assessment_state = 'COMPLETED',
        completed_at = NOW(),
        risk_score = v_risk_score,
        compliant = v_compliant
    WHERE assessment_id = p_assessment_id;

    result_risk_score := v_risk_score;
    result_compliant := v_compliant;

    RETURN NEXT;
END;
$$;

-- ============================================================
-- 11. ASSET ASSESSMENT PROCEDURE
-- ============================================================

CREATE OR REPLACE PROCEDURE assess_cloud_asset(
    p_asset_id BIGINT,
    p_policy_id BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_model service_model;
    v_version INTEGER;
    v_status asset_state;
    v_assessment_id BIGINT;
    v_rule RECORD;
    v_compliant BOOLEAN;
    v_value BOOLEAN;
BEGIN
    SELECT
        cs.model,
        ca.version_number,
        ca.asset_status

    INTO
        v_model,
        v_version,
        v_status

    FROM cloud_assets ca
    JOIN cloud_services cs
      ON cs.service_id = ca.service_id

    WHERE ca.asset_id = p_asset_id
    FOR UPDATE OF ca;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Cloud asset not found';
    END IF;

    IF v_status <> 'ACTIVE' THEN
        RAISE EXCEPTION
            'Only active assets can be assessed';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM security_policies
        WHERE policy_id = p_policy_id
          AND is_active = TRUE
          AND effective_from <= CURRENT_DATE
          AND (
              effective_until IS NULL
              OR effective_until >= CURRENT_DATE
          )
    ) THEN
        RAISE EXCEPTION
            'Policy is inactive or outside its effective period';
    END IF;

    INSERT INTO security_assessments (
        asset_id,
        policy_id,
        assessed_asset_version
    )
    VALUES (
        p_asset_id,
        p_policy_id,
        v_version
    )
    RETURNING assessment_id INTO v_assessment_id;

    FOR v_rule IN
        SELECT
            pr.control_id,
            pr.required,
            pr.applies_to,
            pr.remediation_guidance,
            sc.severity,
            sc.control_code,
            sc.control_name,
            ra.responsibility

        FROM policy_rules pr

        JOIN security_controls sc
          ON sc.control_id = pr.control_id

        JOIN responsibility_assignments ra
          ON ra.control_id = pr.control_id
         AND ra.service_model = v_model

        WHERE pr.policy_id = p_policy_id
          AND sc.is_active = TRUE
          AND v_model = ANY(pr.applies_to)
    LOOP

        v_compliant := TRUE;

        IF v_rule.required THEN

            CASE v_rule.control_code

                WHEN 'ENCRYPTION_AT_REST' THEN
                    SELECT encryption_at_rest
                    INTO v_value
                    FROM cloud_assets
                    WHERE asset_id = p_asset_id;

                WHEN 'ENCRYPTION_IN_TRANSIT' THEN
                    SELECT encryption_in_transit
                    INTO v_value
                    FROM cloud_assets
                    WHERE asset_id = p_asset_id;

                WHEN 'MFA' THEN
                    SELECT mfa_enabled
                    INTO v_value
                    FROM cloud_assets
                    WHERE asset_id = p_asset_id;

                WHEN 'LOGGING' THEN
                    SELECT logging_enabled
                    INTO v_value
                    FROM cloud_assets
                    WHERE asset_id = p_asset_id;

                WHEN 'BACKUP' THEN
                    SELECT backup_enabled
                    INTO v_value
                    FROM cloud_assets
                    WHERE asset_id = p_asset_id;

                WHEN 'LEAST_PRIVILEGE' THEN
                    SELECT least_privilege_enabled
                    INTO v_value
                    FROM cloud_assets
                    WHERE asset_id = p_asset_id;

                WHEN 'PUBLIC_ACCESS' THEN
                    SELECT NOT (
                        public_access
                        AND environment = 'PRODUCTION'
                    )
                    INTO v_value
                    FROM cloud_assets
                    WHERE asset_id = p_asset_id;

                WHEN 'GUEST_OS_PATCHING' THEN
                    SELECT patching_enabled
                    INTO v_value
                    FROM cloud_assets
                    WHERE asset_id = p_asset_id;

                ELSE
                    RAISE EXCEPTION
                        'No evaluator for control %',
                        v_rule.control_code;

            END CASE;

            v_compliant := COALESCE(v_value, FALSE);

        END IF;

        INSERT INTO security_findings (
            assessment_id,
            control_id,
            responsibility,
            severity,
            is_compliant,
            finding_status,
            evidence,
            remediation
        )
        VALUES (
            v_assessment_id,
            v_rule.control_id,
            v_rule.responsibility,
            v_rule.severity,
            v_compliant,
            CASE
                WHEN v_compliant THEN 'RESOLVED'::finding_state
                ELSE 'OPEN'::finding_state
            END,
            CASE
                WHEN v_compliant THEN 'Control passed'
                ELSE 'Control failed'
            END,
            v_rule.remediation_guidance
        );

    END LOOP;

    PERFORM *
    FROM complete_security_assessment(v_assessment_id);

    RAISE NOTICE
        'Assessment % completed for asset %',
        v_assessment_id,
        p_asset_id;

END;
$$;

-- ============================================================
-- 12. REPORTING VIEWS
-- ============================================================

CREATE VIEW v_cloud_asset_inventory AS
SELECT
    ca.asset_id,
    ca.asset_code,
    ca.asset_name,
    o.organization_name,
    cp.provider_name,
    cs.service_name,
    cs.model,
    ca.environment,
    ca.region,
    ca.data_classification,
    ca.asset_status,
    ca.public_access,
    ca.encryption_at_rest,
    ca.encryption_in_transit,
    ca.mfa_enabled,
    ca.logging_enabled,
    ca.backup_enabled,
    ca.least_privilege_enabled,
    ca.patching_enabled,
    ca.version_number
FROM cloud_assets ca
JOIN organizations o
  ON o.organization_id = ca.organization_id
JOIN cloud_services cs
  ON cs.service_id = ca.service_id
JOIN cloud_providers cp
  ON cp.provider_id = cs.provider_id;

CREATE VIEW v_latest_security_assessments AS
SELECT DISTINCT ON (sa.asset_id)
    sa.assessment_id,
    sa.asset_id,
    ca.asset_code,
    ca.asset_name,
    sa.assessment_state,
    sa.assessed_at,
    sa.risk_score,
    sa.compliant,
    sa.policy_id
FROM security_assessments sa
JOIN cloud_assets ca
  ON ca.asset_id = sa.asset_id
ORDER BY
    sa.asset_id,
    sa.assessed_at DESC,
    sa.assessment_id DESC;

CREATE VIEW v_open_security_findings AS
SELECT
    sf.finding_id,
    ca.asset_code,
    ca.asset_name,
    sc.control_code,
    sc.control_name,
    sf.responsibility,
    sf.severity,
    sf.finding_status,
    sf.remediation,
    sf.detected_at
FROM security_findings sf
JOIN security_assessments sa
  ON sa.assessment_id = sf.assessment_id
JOIN cloud_assets ca
  ON ca.asset_id = sa.asset_id
JOIN security_controls sc
  ON sc.control_id = sf.control_id
WHERE sf.finding_status IN (
    'OPEN',
    'IN_PROGRESS'
);

-- ============================================================
-- 13. SEED DATA
-- ============================================================

INSERT INTO organizations (organization_name)
VALUES
    ('Enterprise Technology Division'),
    ('Research and Development Division');

INSERT INTO cloud_providers (provider_name)
VALUES
    ('AWS'),
    ('Microsoft Azure'),
    ('Google Cloud');

INSERT INTO cloud_services (
    provider_id,
    service_name,
    model,
    description
)
SELECT
    provider_id,
    'EC2 Virtual Machines',
    'IaaS',
    'Virtual machine infrastructure'
FROM cloud_providers
WHERE provider_name = 'AWS';

INSERT INTO cloud_services (
    provider_id,
    service_name,
    model,
    description
)
SELECT
    provider_id,
    'Managed Application Platform',
    'PaaS',
    'Managed application runtime'
FROM cloud_providers
WHERE provider_name = 'Microsoft Azure';

INSERT INTO cloud_services (
    provider_id,
    service_name,
    model,
    description
)
SELECT
    provider_id,
    'Enterprise Document Service',
    'SaaS',
    'Hosted enterprise document management'
FROM cloud_providers
WHERE provider_name = 'Google Cloud';

INSERT INTO security_domains (
    domain_code,
    domain_name
)
VALUES
    ('INFRASTRUCTURE', 'Infrastructure Security'),
    ('IDENTITY', 'Identity and Access Security'),
    ('DATA', 'Data Protection'),
    ('OPERATIONS', 'Security Operations'),
    ('APPLICATION', 'Application Security');

INSERT INTO security_controls (
    control_code,
    domain_id,
    control_name,
    description,
    severity
)
SELECT
    'ENCRYPTION_AT_REST',
    domain_id,
    'Encryption at Rest',
    'Protect stored data using encryption',
    'HIGH'
FROM security_domains
WHERE domain_code = 'DATA';

INSERT INTO security_controls (
    control_code,
    domain_id,
    control_name,
    description,
    severity
)
SELECT
    'ENCRYPTION_IN_TRANSIT',
    domain_id,
    'Encryption in Transit',
    'Protect data during transmission',
    'HIGH'
FROM security_domains
WHERE domain_code = 'DATA';

INSERT INTO security_controls (
    control_code,
    domain_id,
    control_name,
    description,
    severity
)
SELECT
    'MFA',
    domain_id,
    'Multi-Factor Authentication',
    'Require multiple authentication factors',
    'CRITICAL'
FROM security_domains
WHERE domain_code = 'IDENTITY';

INSERT INTO security_controls (
    control_code,
    domain_id,
    control_name,
    description,
    severity
)
SELECT
    'LOGGING',
    domain_id,
    'Security Event Logging',
    'Collect and monitor security events',
    'HIGH'
FROM security_domains
WHERE domain_code = 'OPERATIONS';

INSERT INTO security_controls (
    control_code,
    domain_id,
    control_name,
    description,
    severity
)
SELECT
    'BACKUP',
    domain_id,
    'Backup Protection',
    'Protect backups and recovery processes',
    'HIGH'
FROM security_domains
WHERE domain_code = 'OPERATIONS';

INSERT INTO security_controls (
    control_code,
    domain_id,
    control_name,
    description,
    severity
)
SELECT
    'LEAST_PRIVILEGE',
    domain_id,
    'Least Privilege',
    'Grant minimum necessary permissions',
    'HIGH'
FROM security_domains
WHERE domain_code = 'IDENTITY';

INSERT INTO security_controls (
    control_code,
    domain_id,
    control_name,
    description,
    severity
)
SELECT
    'PUBLIC_ACCESS',
    domain_id,
    'Public Access Restriction',
    'Prevent unintended public exposure',
    'CRITICAL'
FROM security_domains
WHERE domain_code = 'INFRASTRUCTURE';

INSERT INTO security_controls (
    control_code,
    domain_id,
    control_name,
    description,
    severity
)
SELECT
    'GUEST_OS_PATCHING',
    domain_id,
    'Guest OS Patching',
    'Maintain guest operating system security',
    'HIGH'
FROM security_domains
WHERE domain_code = 'INFRASTRUCTURE';

-- Service-specific responsibility assignments.

INSERT INTO responsibility_assignments (
    service_model,
    control_id,
    responsibility,
    responsibility_description
)
SELECT
    model,
    control_id,
    CASE
        WHEN control_code IN (
            'ENCRYPTION_IN_TRANSIT',
            'LOGGING',
            'BACKUP'
        ) THEN 'SHARED'::responsibility_owner

        ELSE 'CUSTOMER'::responsibility_owner
    END,
    'Customer and provider responsibilities depend on service configuration.'
FROM security_controls
CROSS JOIN (
    VALUES
        ('IaaS'::service_model),
        ('PaaS'::service_model),
        ('SaaS'::service_model)
) AS models(model);

-- Guest operating system management is customer-owned in IaaS.
-- It is generally provider-managed in PaaS and SaaS.

INSERT INTO responsibility_assignments (
    service_model,
    control_id,
    responsibility,
    responsibility_description
)
SELECT
    'IaaS',
    control_id,
    'CUSTOMER',
    'Customer maintains the guest operating system.'
FROM security_controls
WHERE control_code = 'GUEST_OS_PATCHING';

INSERT INTO responsibility_assignments (
    service_model,
    control_id,
    responsibility,
    responsibility_description
)
SELECT
    model,
    control_id,
    'PROVIDER',
    'Provider manages the underlying operating system.'
FROM security_controls
CROSS JOIN (
    VALUES
        ('PaaS'::service_model),
        ('SaaS'::service_model)
) AS models(model)
WHERE control_code = 'GUEST_OS_PATCHING';

-- Provider responsibility for physical infrastructure is not
-- configurable through the customer asset inventory.
-- The provider-side ownership is recorded explicitly.

INSERT INTO security_controls (
    control_code,
    domain_id,
    control_name,
    description,
    severity
)
SELECT
    'PHYSICAL_SECURITY',
    domain_id,
    'Physical Infrastructure Security',
    'Data center physical security and hardware protection',
    'CRITICAL'
FROM security_domains
WHERE domain_code = 'INFRASTRUCTURE';

INSERT INTO responsibility_assignments (
    service_model,
    control_id,
    responsibility,
    responsibility_description
)
SELECT
    model,
    control_id,
    'PROVIDER',
    'Provider protects physical facilities and infrastructure.'
FROM security_controls
CROSS JOIN (
    VALUES
        ('IaaS'::service_model),
        ('PaaS'::service_model),
        ('SaaS'::service_model)
) AS models(model)
WHERE control_code = 'PHYSICAL_SECURITY';

-- Active security policy.

INSERT INTO security_policies (
    policy_name,
    policy_version,
    description,
    effective_from,
    is_active
)
VALUES (
    'Enterprise Cloud Security Baseline',
    '1.0',
    'Minimum cloud security configuration requirements',
    CURRENT_DATE,
    TRUE
);

INSERT INTO policy_rules (
    policy_id,
    control_id,
    required,
    applies_to,
    remediation_guidance
)
SELECT
    p.policy_id,
    sc.control_id,
    TRUE,
    ARRAY[
        'IaaS'::service_model,
        'PaaS'::service_model,
        'SaaS'::service_model
    ],
    CASE sc.control_code
        WHEN 'ENCRYPTION_AT_REST'
            THEN 'Enable storage encryption.'
        WHEN 'ENCRYPTION_IN_TRANSIT'
            THEN 'Require TLS.'
        WHEN 'MFA'
            THEN 'Enable MFA.'
        WHEN 'LOGGING'
            THEN 'Enable security logging.'
        WHEN 'BACKUP'
            THEN 'Configure protected backups.'
        WHEN 'LEAST_PRIVILEGE'
            THEN 'Restrict permissions.'
        WHEN 'PUBLIC_ACCESS'
            THEN 'Restrict public production access.'
        ELSE 'Review the security control.'
    END
FROM security_policies p
CROSS JOIN security_controls sc
WHERE p.policy_name = 'Enterprise Cloud Security Baseline'
  AND sc.control_code IN (
      'ENCRYPTION_AT_REST',
      'ENCRYPTION_IN_TRANSIT',
      'MFA',
      'LOGGING',
      'BACKUP',
      'LEAST_PRIVILEGE',
      'PUBLIC_ACCESS'
  );

INSERT INTO policy_rules (
    policy_id,
    control_id,
    required,
    applies_to,
    remediation_guidance
)
SELECT
    p.policy_id,
    sc.control_id,
    TRUE,
    ARRAY['IaaS'::service_model],
    'Apply and verify guest operating system security patches.'
FROM security_policies p
CROSS JOIN security_controls sc
WHERE p.policy_name = 'Enterprise Cloud Security Baseline'
  AND sc.control_code = 'GUEST_OS_PATCHING';

-- ============================================================
-- 14. CLOUD ASSET SAMPLE RECORDS
-- ============================================================

INSERT INTO cloud_assets (
    organization_id,
    service_id,
    asset_code,
    asset_name,
    environment,
    region,
    data_classification,
    public_access,
    encryption_at_rest,
    encryption_in_transit,
    mfa_enabled,
    logging_enabled,
    backup_enabled,
    least_privilege_enabled,
    patching_enabled
)
SELECT
    o.organization_id,
    cs.service_id,
    'AWS-EC2-001',
    'Production API Server',
    'PRODUCTION',
    'ap-south-1',
    'CONFIDENTIAL',
    FALSE,
    TRUE,
    TRUE,
    TRUE,
    TRUE,
    TRUE,
    TRUE,
    TRUE
FROM organizations o
CROSS JOIN cloud_services cs
WHERE o.organization_name = 'Enterprise Technology Division'
  AND cs.service_name = 'EC2 Virtual Machines';

INSERT INTO cloud_assets (
    organization_id,
    service_id,
    asset_code,
    asset_name,
    environment,
    region,
    data_classification,
    public_access,
    encryption_at_rest,
    encryption_in_transit,
    mfa_enabled,
    logging_enabled,
    backup_enabled,
    least_privilege_enabled,
    patching_enabled
)
SELECT
    o.organization_id,
    cs.service_id,
    'AZURE-APP-002',
    'Managed Application Platform',
    'PRODUCTION',
    'centralindia',
    'INTERNAL',
    FALSE,
    TRUE,
    TRUE,
    FALSE,
    TRUE,
    TRUE,
    FALSE,
    FALSE
FROM organizations o
CROSS JOIN cloud_services cs
WHERE o.organization_name = 'Enterprise Technology Division'
  AND cs.service_name = 'Managed Application Platform';

INSERT INTO cloud_assets (
    organization_id,
    service_id,
    asset_code,
    asset_name,
    environment,
    region,
    data_classification,
    public_access,
    encryption_at_rest,
    encryption_in_transit,
    mfa_enabled,
    logging_enabled,
    backup_enabled,
    least_privilege_enabled,
    patching_enabled
)
SELECT
    o.organization_id,
    cs.service_id,
    'SAAS-003',
    'Enterprise Document Platform',
    'PRODUCTION',
    'asia-south1',
    'RESTRICTED',
    TRUE,
    TRUE,
    TRUE,
    FALSE,
    FALSE,
    FALSE,
    FALSE,
    FALSE
FROM organizations o
CROSS JOIN cloud_services cs
WHERE o.organization_name = 'Research and Development Division'
  AND cs.service_name = 'Enterprise Document Service';

-- ============================================================
-- 15. EXECUTE ASSESSMENTS TRANSACTIONALLY
-- ============================================================

DO $$
DECLARE
    v_policy_id BIGINT;
    v_asset RECORD;
BEGIN
    SELECT policy_id
    INTO v_policy_id
    FROM security_policies
    WHERE policy_name = 'Enterprise Cloud Security Baseline';

    FOR v_asset IN
        SELECT asset_id
        FROM cloud_assets
        WHERE asset_status = 'ACTIVE'
        ORDER BY asset_id
    LOOP
        CALL assess_cloud_asset(
            v_asset.asset_id,
            v_policy_id
        );
    END LOOP;
END;
$$;

-- ============================================================
-- 16. RETRIEVAL QUERIES
-- ============================================================

-- Complete asset inventory.

SELECT *
FROM v_cloud_asset_inventory
ORDER BY organization_name, asset_code;

-- Find production assets exposed to the public internet.

SELECT
    asset_code,
    asset_name,
    model,
    region,
    data_classification
FROM v_cloud_asset_inventory
WHERE environment = 'PRODUCTION'
  AND public_access = TRUE
  AND asset_status = 'ACTIVE';

-- ============================================================
-- 17. VALIDATION QUERIES
-- ============================================================

-- Verify responsibility mapping by service model.

SELECT
    ra.service_model,
    sc.control_code,
    sc.control_name,
    ra.responsibility
FROM responsibility_assignments ra
JOIN security_controls sc
  ON sc.control_id = ra.control_id
ORDER BY ra.service_model, sc.control_code;

-- Identify assets missing mandatory controls.

SELECT
    asset_code,
    asset_name,
    model,
    ARRAY_REMOVE(
        ARRAY[
            CASE WHEN NOT encryption_at_rest
                THEN 'Encryption at rest' END,
            CASE WHEN NOT encryption_in_transit
                THEN 'Encryption in transit' END,
            CASE WHEN NOT mfa_enabled
                THEN 'MFA' END,
            CASE WHEN NOT logging_enabled
                THEN 'Logging' END,
            CASE WHEN NOT backup_enabled
                THEN 'Backup' END,
            CASE WHEN NOT least_privilege_enabled
                THEN 'Least privilege' END,
            CASE WHEN model = 'IaaS' AND NOT patching_enabled
                THEN 'Guest OS patching' END,
            CASE WHEN public_access
                      AND environment = 'PRODUCTION'
                THEN 'Public production exposure' END
        ],
        NULL
    ) AS missing_controls
FROM v_cloud_asset_inventory
WHERE asset_status = 'ACTIVE';

-- ============================================================
-- 18. AGGREGATION AND RISK REPORTING
-- ============================================================

-- Compliance distribution by service model.

SELECT
    cs.model,
    COUNT(*) AS total_assets,
    COUNT(*) FILTER (
        WHERE lsa.compliant = TRUE
    ) AS compliant_assets,
    COUNT(*) FILTER (
        WHERE lsa.compliant = FALSE
    ) AS non_compliant_assets,
    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE lsa.compliant = TRUE
        ) / NULLIF(COUNT(*), 0),
        2
    ) AS compliance_percentage
FROM cloud_assets ca
JOIN cloud_services cs
  ON cs.service_id = ca.service_id
LEFT JOIN v_latest_security_assessments lsa
  ON lsa.asset_id = ca.asset_id
GROUP BY cs.model
ORDER BY cs.model;

-- Risk distribution by severity.

SELECT
    severity,
    COUNT(*) AS finding_count
FROM security_findings
WHERE finding_status IN ('OPEN', 'IN_PROGRESS')
GROUP BY severity
ORDER BY
    CASE severity
        WHEN 'CRITICAL' THEN 1
        WHEN 'HIGH' THEN 2
        WHEN 'MEDIUM' THEN 3
        WHEN 'LOW' THEN 4
    END;

-- Highest-risk cloud assets.

SELECT
    ca.asset_code,
    ca.asset_name,
    cs.model,
    sa.risk_score,
    sa.compliant,
    sa.assessed_at
FROM v_latest_security_assessments sa
JOIN cloud_assets ca
  ON ca.asset_id = sa.asset_id
JOIN cloud_services cs
  ON cs.service_id = ca.service_id
ORDER BY sa.risk_score DESC, sa.assessed_at DESC;

-- ============================================================
-- 19. CTE-BASED FINDING ANALYSIS
-- ============================================================

WITH finding_summary AS (
    SELECT
        sa.asset_id,
        COUNT(*) FILTER (
            WHERE sf.finding_status IN ('OPEN', 'IN_PROGRESS')
        ) AS open_findings,

        COUNT(*) FILTER (
            WHERE sf.severity = 'CRITICAL'
              AND sf.finding_status IN ('OPEN', 'IN_PROGRESS')
        ) AS critical_findings,

        COUNT(*) FILTER (
            WHERE sf.severity = 'HIGH'
              AND sf.finding_status IN ('OPEN', 'IN_PROGRESS')
        ) AS high_findings

    FROM security_assessments sa
    LEFT JOIN security_findings sf
      ON sf.assessment_id = sa.assessment_id

    WHERE sa.assessment_state = 'COMPLETED'

    GROUP BY sa.asset_id
)

SELECT
    ca.asset_code,
    ca.asset_name,
    fs.open_findings,
    fs.critical_findings,
    fs.high_findings,

    CASE
        WHEN fs.critical_findings > 0 THEN 'IMMEDIATE ACTION'
        WHEN fs.high_findings > 0 THEN 'PRIORITY ACTION'
        WHEN fs.open_findings > 0 THEN 'REMEDIATION REQUIRED'
        ELSE 'NO OPEN FINDINGS'
    END AS operational_priority

FROM finding_summary fs
JOIN cloud_assets ca
  ON ca.asset_id = fs.asset_id
ORDER BY
    fs.critical_findings DESC,
    fs.high_findings DESC,
    fs.open_findings DESC;

-- ============================================================
-- 20. ELIGIBILITY DETERMINATION
-- ============================================================

-- Determine whether each asset meets the baseline policy.
-- Eligibility here means assessment compliance, not a legal
-- or regulatory certification.

SELECT
    ca.asset_code,
    ca.asset_name,
    sa.assessment_id,

    CASE
        WHEN ca.asset_status <> 'ACTIVE'
            THEN 'INELIGIBLE: INACTIVE ASSET'

        WHEN sa.assessment_state <> 'COMPLETED'
            THEN 'INELIGIBLE: ASSESSMENT INCOMPLETE'

        WHEN sa.compliant = TRUE
            THEN 'ELIGIBLE'

        ELSE 'INELIGIBLE: SECURITY FINDINGS'
    END AS deployment_eligibility

FROM cloud_assets ca
LEFT JOIN v_latest_security_assessments sa
  ON sa.asset_id = ca.asset_id
ORDER BY ca.asset_code;

-- ============================================================
-- 21. WORKFLOW PROCESSING
-- ============================================================

-- Move a finding into remediation.

UPDATE security_findings
SET finding_status = 'IN_PROGRESS'
WHERE finding_id = (
    SELECT finding_id
    FROM security_findings
    WHERE finding_status = 'OPEN'
    ORDER BY
        CASE severity
            WHEN 'CRITICAL' THEN 1
            WHEN 'HIGH' THEN 2
            WHEN 'MEDIUM' THEN 3
            WHEN 'LOW' THEN 4
        END,
        detected_at
    LIMIT 1
)
AND finding_status = 'OPEN';

-- ============================================================
-- 22. FAILURE CASE VALIDATION
-- ============================================================

-- The following transaction intentionally attempts to insert
-- a duplicate asset code. The exception is caught so the script
-- continues without compromising the existing inventory.

DO $$
BEGIN
    BEGIN
        INSERT INTO cloud_assets (
            organization_id,
            service_id,
            asset_code,
            asset_name,
            environment,
            region,
            data_classification
        )
        SELECT
            organization_id,
            service_id,
            'AWS-EC2-001',
            'Duplicate Asset',
            'DEVELOPMENT',
            'ap-south-1',
            'INTERNAL'
        FROM cloud_assets
        LIMIT 1;

    EXCEPTION
        WHEN unique_violation THEN
            RAISE NOTICE
                'Expected failure: duplicate asset code rejected';
    END;
END;
$$;

-- ============================================================
-- 23. AUDIT HISTORY RETRIEVAL
-- ============================================================

SELECT
    log_id,
    asset_id,
    action,
    changed_at,
    database_user
FROM security_audit_log
ORDER BY changed_at DESC;

-- ============================================================
-- 24. DATABASE INTEGRITY CHECKS
-- ============================================================

DO $$
DECLARE
    v_invalid_count BIGINT;
BEGIN
    SELECT COUNT(*)
    INTO v_invalid_count
    FROM security_assessments sa
    JOIN cloud_assets ca
      ON ca.asset_id = sa.asset_id
    WHERE sa.assessed_asset_version > ca.version_number;

    IF v_invalid_count > 0 THEN
        RAISE WARNING
            'Some assessments reference unexpected asset versions';
    END IF;

    RAISE NOTICE
        'Cloud security integrity validation completed';
END;
$$;

COMMIT;
```

```markdown
# Cloud Security Fundamentals

## 1. Domain Overview

Cloud security is the protection of cloud-hosted infrastructure, applications, identities, networks, workloads, and information against unauthorized access, misuse, disruption, alteration, and disclosure.

Cloud security requires cooperation between the cloud service provider and the customer.

The provider operates the cloud platform and protects its underlying infrastructure. The customer configures and uses cloud services securely, manages access to organizational resources, and protects workloads and information according to the service agreement.

The implementations in this project model three cloud service models:

| Service model | Full form | Main characteristics |
|---|---|---|
| IaaS | Infrastructure as a Service | Customer manages virtual machines, guest operating systems, applications, and data. |
| PaaS | Platform as a Service | Provider manages the infrastructure and managed runtime platform. Customer manages applications, data, and access configuration. |
| SaaS | Software as a Service | Provider operates the application platform. Customer manages organizational users, access configuration, information, and service-specific settings. |

The precise responsibility boundary depends on the provider, service configuration, contractual terms, and deployment architecture.

## 2. Shared Responsibility Model

The shared responsibility model defines the security responsibilities of cloud providers and customers.

It prevents the assumption that purchasing a managed cloud service transfers every security obligation to the provider.

### 2.1 Provider responsibilities

Typical provider responsibilities include:

- Physical data center protection.
- Physical access controls.
- Hardware maintenance.
- Hypervisor security.
- Underlying infrastructure availability.
- Security of provider-operated platform components.
- Protection of the cloud control plane.
- Infrastructure-level monitoring.

### 2.2 Customer responsibilities

Typical customer responsibilities include:

- Identity and access configuration.
- User account administration.
- Application security.
- Data classification.
- Secure application development.
- Workload configuration.
- Permission management.
- Customer-managed encryption configuration.
- Guest operating system maintenance in IaaS.
- Backup configuration and recovery planning.
- Security monitoring configuration.

### 2.3 Shared responsibilities

Some controls involve both parties.

| Security area | Provider responsibility | Customer responsibility |
|---|---|---|
| Identity | Identity platform availability and underlying security | Users, authentication settings, permissions and MFA configuration |
| Network | Underlying network infrastructure | Network segmentation, firewall rules and traffic restrictions |
| Data protection | Platform encryption capabilities and infrastructure protection | Data classification, access restrictions and encryption configuration |
| Logging | Provider-generated infrastructure telemetry | Enabling relevant logs, collecting events and investigating alerts |
| Backup | Service-specific backup infrastructure | Backup policies, retention, recovery requirements and restoration testing |
| Security monitoring | Provider infrastructure monitoring | Customer workload monitoring and incident response |

The responsibility mapping in the Python, JavaScript, C++17 and Java implementations is an educational model. Real deployments require service-specific responsibility verification.

### 2.4 Responsibility by service model

| Component | IaaS | PaaS | SaaS |
|---|---|---|---|
| Physical data center | Provider | Provider | Provider |
| Physical hardware | Provider | Provider | Provider |
| Hypervisor | Provider | Provider | Provider |
| Guest operating system | Customer | Provider | Provider |
| Managed runtime | Customer-managed | Provider | Provider |
| Application | Customer | Customer | Provider |
| Customer information | Customer | Customer | Customer |
| User access configuration | Customer | Customer | Customer |
| Infrastructure networking | Provider | Provider | Provider |
| Customer network configuration | Customer | Customer | Service-dependent |

A provider may expose configuration options that change the practical responsibility boundary. The table represents a simplified conventional model rather than a universal contractual allocation.

## 3. Infrastructure as a Service

IaaS provides virtualized computing resources such as:

- Virtual machines.
- Virtual networks.
- Block storage.
- Object storage.
- Network interfaces.
- Load balancers.

The customer has substantial control over the operating environment.

### Security requirements

The customer should:

- Harden guest operating systems.
- Apply security patches.
- Restrict administrative access.
- Configure firewalls and network segmentation.
- Encrypt stored information.
- Require encrypted communications.
- Enable workload monitoring.
- Maintain protected backups.

The Python and C++17 implementations specifically evaluate guest operating system patching for IaaS assets.

This requirement is not applied automatically to PaaS and SaaS assets because the underlying operating system is normally provider-managed in those models.

## 4. Platform as a Service

PaaS provides managed application development and execution environments.

The provider generally manages:

- Infrastructure.
- Operating systems.
- Runtime infrastructure.
- Platform maintenance.
- Managed service availability.

The customer generally manages:

- Application code.
- Application vulnerabilities.
- Application identities.
- Data access.
- Application configuration.
- Secrets and credentials.
- Service permissions.

A managed application platform does not automatically make an application secure.

For example, a PaaS application can remain vulnerable if excessive permissions, insecure authentication, exposed endpoints, or unsafe application logic are present.

## 5. Software as a Service

SaaS delivers a complete application through a provider-operated service.

Examples of customer security responsibilities include:

- Managing user accounts.
- Enforcing MFA where supported.
- Restricting external sharing.
- Reviewing administrative privileges.
- Classifying organizational information.
- Configuring retention and access policies.
- Monitoring account activity.
- Reviewing third-party integrations.

The provider operates the application infrastructure, but customer account misuse and unsafe sharing configurations can still expose organizational information.

## 6. Core Cloud Security Principles

### 6.1 Least privilege

Every identity should receive only the permissions necessary to perform its assigned responsibilities.

An identity with read-only access should not automatically receive administrative permissions.

Practical controls:

- Role-based access control.
- Attribute-based access control.
- Temporary privileged access.
- Permission reviews.
- Removal of unused credentials.
- Separation of administrative and normal accounts.

The implementations evaluate the `leastPrivilege` configuration.

### 6.2 Defense in depth

Defense in depth applies multiple independent security controls.

A cloud workload should not depend on a single security mechanism.

Example architecture:

Internet
  |
Web Application Firewall
  |
Network Access Controls
  |
Application Gateway
  |
Private Application Subnet
  |
Database Subnet
  |
Encrypted Storage

Additional controls include:

- Identity verification.
- MFA.
- Endpoint protection.
- Encryption.
- Centralized logging.
- Backup isolation.
- Incident response.

Failure of one control should not automatically expose every other component.

### 6.3 Zero Trust

Zero Trust is based on the principle that access should not be granted merely because a user or workload is located inside a trusted network.

Access decisions should consider:

- Identity.
- Authentication strength.
- Device condition.
- Requested resource.
- Permission level.
- Context.
- Risk signals.
- Session validity.

Important mechanisms include continuous verification, narrowly scoped authorization, and monitoring.

### 6.4 Encryption

Encryption protects information against unauthorized disclosure.

Two important categories are:

| Category | Protection |
|---|---|
| Encryption at rest | Protects stored information |
| Encryption in transit | Protects information during transmission |

Encryption at rest may use managed encryption keys or customer-managed keys.

Encryption in transit generally requires properly configured TLS.

Key-management considerations include:

- Key rotation.
- Access restrictions.
- Key storage.
- Separation of duties.
- Key recovery.
- Revocation.
- Audit logging.

Encryption does not replace authorization. An authorized application or compromised identity may still access decrypted information.

### 6.5 Secure configuration

Cloud services frequently expose configuration options that affect their security.

Examples include:

- Public storage access.
- Open network ports.
- Weak authentication requirements.
- Excessive identity permissions.
- Missing logging.
- Unencrypted storage.
- Unprotected backups.

Secure configuration requires continuous assessment rather than a one-time deployment review.

### 6.6 Security monitoring

Monitoring identifies suspicious activity and security control failures.

Relevant events include:

- Failed authentication.
- Privileged account creation.
- Permission changes.
- Public resource exposure.
- Unusual API calls.
- Configuration modifications.
- Data access anomalies.
- Security policy violations.

Centralized logging provides a consistent source of evidence for security investigations.

### 6.7 Backup and recovery

Backups support recovery from:

- Accidental deletion.
- Infrastructure failure.
- Application corruption.
- Ransomware.
- Malicious modification.
- Operational errors.

A secure backup design considers:

- Backup encryption.
- Access restrictions.
- Retention periods.
- Recovery point objectives.
- Recovery time objectives.
- Offline or immutable backup copies.
- Restoration testing.

A successful backup operation does not prove that restoration will succeed.

## 7. Identity and Access Management

Identity and Access Management controls who can access cloud resources and what actions they can perform.

### Authentication

Authentication establishes the identity of a user, service, or workload.

Common mechanisms include:

- Password authentication.
- Multi-factor authentication.
- Hardware security keys.
- Federated identity.
- Certificates.
- Workload identities.

### Authorization

Authorization determines which actions an authenticated identity can perform.

Examples:

- Read a storage object.
- Modify a virtual machine.
- Create a network.
- Change a security policy.
- Manage encryption keys.

### Role-based access control

RBAC associates permissions with roles.

Example:

| Role | Permissions |
|---|---|
| Security auditor | Read security configuration and reports |
| Application developer | Deploy approved application components |
| Cloud administrator | Manage assigned infrastructure |
| Backup operator | Execute authorized backup and recovery operations |

### Multi-factor authentication

MFA requires more than one authentication factor.

It reduces the impact of stolen passwords, although it does not eliminate phishing, session theft, or compromised devices.

The implementations treat missing MFA as a critical finding.

## 8. Cloud Security Policy Evaluation

A security policy defines the conditions that cloud assets must satisfy.

The project uses a common set of baseline controls:

| Control | Requirement | Default severity |
|---|---|---|
| Encryption at rest | Storage encryption enabled | High |
| Encryption in transit | Secure network communication | High |
| MFA | Multi-factor authentication enabled | Critical |
| Logging | Security event collection enabled | High |
| Backup | Protected backup configured | High |
| Least privilege | Excessive permissions restricted | High |
| Public access | Unintended production exposure prohibited | Critical |
| Guest OS patching | IaaS operating system maintained | High |

The evaluation process is:

Asset registration
  |
Service model identification
  |
Policy selection
  |
Applicable control selection
  |
Configuration evaluation
  |
Finding generation
  |
Risk calculation
  |
Security report

The implementations use Boolean configuration values to represent simplified control evidence.

A production assessment should obtain evidence from cloud APIs, configuration inventories, identity systems, monitoring platforms, and independent security testing.

## 9. Risk Scoring

The implementations use a weighted risk score.

| Severity | Weight |
|---|---:|
| Critical | 4 |
| High | 3 |
| Medium | 2 |
| Low | 1 |

Risk score:

Risk Score = Sum of the weights of non-compliant findings.

For example:

- One critical finding: 4.
- Two high findings: 6.
- One medium finding: 2.

Total risk score = 12.

This scoring method is suitable for demonstration and prioritization.

It is not a complete quantitative risk model. It does not account for threat likelihood, exploitability, asset exposure, financial impact, or correlations between findings.

An enterprise risk model should incorporate those factors.

## 10. Python Implementation

The Python script implements an object-oriented cloud security assessment platform.

### Main components

| Component | Responsibility |
|---|---|
| `ServiceModel` | Represents IaaS, PaaS and SaaS |
| `Responsibility` | Identifies customer, provider and shared ownership |
| `CloudControl` | Defines security responsibility controls |
| `CloudAsset` | Stores cloud asset configuration |
| `SecurityPolicy` | Defines required security conditions |
| `CloudSecurityAuditor` | Evaluates asset configuration |
| `Finding` | Represents an individual control result |
| `SecurityReport` | Stores assessment results and risk score |
| `CloudSecurityPlatform` | Manages assets and reporting |

### Important mechanisms

The responsibility model distinguishes ownership from compliance.

For example, physical infrastructure security belongs to the provider, while application security belongs to the customer.

Data protection is represented as a shared responsibility.

The auditor evaluates each asset against its applicable controls.

IaaS assets receive an additional guest operating system patching requirement.

The reporting mechanism produces:

- Total assessed assets.
- Compliant assets.
- Non-compliant assets.
- Finding counts.
- Severity distribution.
- Individual remediation guidance.

### File handling

The Python implementation exports assessment results to `cloud_security_audit.json`.

It uses the standard-library `json` and `pathlib` modules.

### Validation

The implementation checks:

- Asset identifiers.
- Asset names.
- Environment values.
- Data classifications.
- Duplicate asset registration.
- Unknown security controls.

Assertions verify secure and insecure asset behavior.

## 11. JavaScript Implementation

The JavaScript implementation provides an event-driven policy evaluation architecture.

### Main components

| Component | Responsibility |
|---|---|
| `CloudAsset` | Maintains asset configuration and lifecycle |
| `ResponsibilityRegistry` | Maps controls to responsibility owners |
| `SecurityRule` | Defines individual policy rules |
| `SecurityPolicyEngine` | Evaluates security configurations |
| `CloudSecurityPlatform` | Manages assets and assessments |
| `SecurityError` | Represents domain-specific failures |

### Event-driven processing

The policy engine extends Node.js `EventEmitter`.

After a completed assessment, it emits `assessmentCompleted`.

The platform listens for this event and reports the asset identifier and calculated risk score.

This separates policy evaluation from operational event handling.

### Asynchronous evaluation

`evaluateAsset()` uses asynchronous rule evaluation and `Promise.all()`.

Independent policy checks can execute concurrently.

The asset version is captured before evaluation and checked again before storing the assessment result.

This prevents an outdated evaluation from being stored as though it represented the latest configuration.

### Asset lifecycle

The implementation supports:

- `ACTIVE`
- `QUARANTINED`
- `RETIRED`

Only active assets can be evaluated or modified.

Quarantine prevents further assessment until an appropriate operational process restores the asset.

### Reporting

The implementation produces a JSON report containing:

- Assessment identifiers.
- Asset identifiers.
- Configuration versions.
- Evaluation timestamps.
- Security findings.
- Risk scores.
- Compliance status.

The export uses restrictive file permissions where supported by the operating system.

## 12. C++17 Implementation

The C++17 implementation focuses on a structured governance and assessment engine.

### Main components

| Component | Responsibility |
|---|---|
| `CloudAsset` | Represents an infrastructure asset |
| `SecurityConfiguration` | Stores security settings |
| `ResponsibilityModel` | Maintains responsibility mappings |
| `SecurityRule` | Defines evaluation conditions |
| `CloudSecurityEngine` | Evaluates asset compliance |
| `Assessment` | Stores findings and risk scores |
| `CloudInventory` | Maintains registered assets |
| `SecurityReporting` | Produces assessment reports |

### Data structures

The program uses:

- `std::map` for deterministic asset and control lookup.
- `std::vector` for security rules and findings.
- `std::set` for applicable service models.
- `std::accumulate` for risk calculations.
- `std::all_of` for compliance verification.
- `std::move` where appropriate to avoid unnecessary copying.

### Complexity

Let:

- A = number of cloud assets.
- R = number of security rules.
- F = number of findings.

An assessment evaluates applicable rules in O(R) time.

Assessing all assets requires O(A × R) time, excluding map lookup and output costs.

Asset lookup in `std::map` takes O(log A) time.

Risk calculation takes O(F) time.

The implementation uses a fixed rule collection, making policy evaluation predictable.

### Failure handling

The program rejects:

- Empty identifiers.
- Empty asset names.
- Duplicate assets.
- Unknown responsibility controls.
- Assessments of inactive assets.

Exceptions prevent invalid domain operations from silently succeeding.

## 13. Java 17 Implementation

The Java implementation uses an enterprise-oriented domain model.

### Main components

| Component | Responsibility |
|---|---|
| `CloudAsset` | Maintains asset state and configuration |
| `SecurityConfiguration` | Immutable security settings |
| `ControlDefinition` | Responsibility ownership |
| `ResponsibilityRegistry` | Control lookup and registration |
| `SecurityRule` | Defines a security requirement |
| `SecurityPolicy` | Stores policy rules |
| `SecurityAssessmentService` | Performs assessment |
| `Assessment` | Stores assessment evidence |
| `CloudInventory` | Manages cloud assets |
| `SecurityReportingService` | Generates enterprise reports |

### Java 17 features

The implementation uses:

- Records for immutable domain structures.
- Enums for controlled state values.
- Collections for asset and control management.
- Streams for filtering and aggregation.
- Switch expressions for policy evaluation.
- `List.copyOf()` for immutable collection snapshots.
- `UUID` for assessment identifiers.
- `Instant` for assessment timestamps.

### State transitions

Cloud assets support:

ACTIVE → QUARANTINED

ACTIVE → RETIRED

QUARANTINED and RETIRED assets cannot be assessed.

This prevents the assessment service from treating inactive resources as normal operational assets.

### Policy separation

The policy defines the rules.

The assessment service evaluates the rules.

The asset maintains its configuration.

The reporting service interprets the assessment results.

This separation improves maintainability and supports future integration with external cloud configuration sources.

## 14. PostgreSQL Implementation

The PostgreSQL script models a relational cloud security governance workflow.

### Database structure

| Table | Purpose |
|---|---|
| `organizations` | Organizational ownership |
| `cloud_providers` | Cloud provider records |
| `cloud_services` | IaaS, PaaS and SaaS service definitions |
| `security_domains` | Security control categories |
| `security_controls` | Individual security requirements |
| `responsibility_assignments` | Ownership by service model |
| `cloud_assets` | Cloud asset inventory |
| `security_policies` | Security baseline definitions |
| `policy_rules` | Individual policy requirements |
| `security_assessments` | Assessment execution and results |
| `security_findings` | Control-level assessment evidence |
| `security_audit_log` | Asset modification history |

### Relational structure

Organizations
  |
  +-- Cloud Assets
          |
          +-- Cloud Services
          |       |
          |       +-- Cloud Providers
          |
          +-- Security Assessments
                  |
                  +-- Security Policies
                  |       |
                  |       +-- Policy Rules
                  |               |
                  |               +-- Security Controls
                  |
                  +-- Security Findings
                          |
                          +-- Security Controls

Security Controls
  |
  +-- Security Domains
  |
  +-- Responsibility Assignments
          |
          +-- Service Models

### Referential integrity

Primary keys identify individual records.

Foreign keys prevent references to nonexistent organizations, services, policies, controls, and assessments.

Unique constraints prevent duplicate asset codes and duplicate control definitions within the relevant policy.

Check constraints enforce valid classifications, positive versions, and valid date ranges.

### Database indexes

The script creates indexes for:

- Organization-based asset retrieval.
- Service-based asset retrieval.
- Environment-based asset filtering.
- Public production asset detection.
- Assessment history.
- Open findings by severity.
- Policy rule retrieval.

Partial indexes reduce the indexed data for queries targeting specific operational states.

### Triggers

`record_asset_change()` records asset creation and modification in `security_audit_log`.

It also increments the asset version automatically.

The trigger prevents changes to immutable asset identity fields and prevents modifications to retired assets.

`validate_finding()` prevents findings from being added to completed or failed assessments.

It also prevents a non-compliant finding from being marked resolved.

### Assessment procedure

`assess_cloud_asset()` performs the main database workflow.

It:

1. Locks the asset record.
2. Checks asset existence.
3. Checks the asset lifecycle state.
4. Verifies that the selected policy is active.
5. Creates an assessment.
6. Retrieves applicable policy rules.
7. Evaluates the corresponding asset configuration.
8. Inserts individual security findings.
9. Calls the assessment completion function.

The completion function calculates the risk score and compliance status.

The workflow runs inside the surrounding transaction.

### Reporting

The database provides views for:

- Cloud asset inventory.
- Latest assessment results.
- Open security findings.

The SQL also demonstrates:

- Retrieval queries.
- Control validation.
- Service-model aggregation.
- Severity distribution.
- CTE-based operational prioritization.
- Deployment eligibility.
- Finding workflow updates.
- Audit history retrieval.

The eligibility query determines whether an asset meets the configured baseline. It does not establish regulatory certification.

## 15. Security Control Failure Scenarios

The following scenarios are represented in the implementations.

| Failure | Security impact | Required response |
|---|---|---|
| MFA disabled | Increased account compromise risk | Enforce MFA and review privileged accounts |
| Public production access | Unauthorized exposure | Restrict network and resource access |
| Storage encryption disabled | Increased information disclosure risk | Enable encryption and review key management |
| TLS not enforced | Communication exposure | Require secure transport |
| Logging disabled | Reduced incident visibility | Enable centralized logging |
| Backups disabled | Reduced recovery capability | Configure and test backups |
| Excessive permissions | Increased attack surface | Apply least privilege |
| IaaS guest OS unpatched | Exposure to known vulnerabilities | Patch and verify the operating system |
| Assessment performed on retired asset | Incorrect operational state | Reject the assessment |

## 16. Important Cloud Security Distinctions

### Security versus compliance

Security refers to the protection of systems and information.

Compliance refers to satisfying specified legal, contractual, regulatory, or organizational requirements.

An asset can pass a simplified technical baseline without being compliant with every applicable regulation.

### Provider security versus customer security

Provider infrastructure security does not guarantee customer workload security.

A securely operated cloud platform can host insecure applications and incorrectly configured resources.

### Encryption versus access control

Encryption protects information through cryptographic mechanisms.

Access control determines which identities can use a resource.

Both are necessary because encryption alone does not prevent authorized but excessive access.

### Availability versus backup

Availability concerns the ability to access a service.

Backup supports restoration of information after data loss or corruption.

A highly available service may still require independent backups.

### Configuration assessment versus continuous monitoring

Configuration assessment evaluates security settings at a particular point in time.

Continuous monitoring observes changes, operational events, and emerging threats.

The implementations provide assessment simulations rather than full continuous cloud monitoring.

## 17. Limitations and Production Considerations

The five source implementations are educational security assessment systems. They demonstrate core cloud security mechanisms without connecting to real cloud accounts.

Important production considerations include:

- Obtain actual resource configurations through authenticated provider APIs.
- Use short-lived credentials and workload identities.
- Protect API credentials and encryption keys.
- Separate security administration from application administration.
- Store assessment evidence securely.
- Use immutable or tamper-resistant audit storage.
- Apply policy versioning.
- Track finding ownership and remediation deadlines.
- Integrate with incident response processes.
- Test backup restoration.
- Validate network exposure continuously.
- Monitor changes to privileged identities.
- Review provider-specific shared responsibility documentation.
- Protect assessment exports from unauthorized access.
- Use concurrency controls for asset configuration updates.
- Implement exception management for approved security deviations.
- Avoid treating missing evidence as proof of compliance.

The simplified implementations use Boolean values for several controls. Real systems require richer evidence, such as encryption key identifiers, TLS configurations, identity policy documents, log retention settings, backup recovery results, and vulnerability scan records.

The PostgreSQL responsibility assignments are illustrative baseline mappings. A production deployment should maintain responsibility assignments for individual cloud services rather than relying only on broad IaaS, PaaS, and SaaS categories.

## 18. Execution Requirements

| Deliverable | Runtime | Dependencies |
|---|---|---|
| Python | Python 3.10+ | Standard library |
| JavaScript | Node.js 18+ | Node.js standard library |
| C++17 | C++17 compiler | Standard library |
| Java | Java 17 | Standard library |
| PostgreSQL | PostgreSQL 14+ | PostgreSQL server |

The Python and JavaScript programs generate JSON assessment reports.

The C++17 program prints governance and assessment results.

The Java program produces enterprise-oriented assessment reports.

The PostgreSQL script creates the database schema, inserts sample records, executes assessments, and runs reporting queries.

The five implementations use the same fundamental security concepts while demonstrating different approaches to domain modeling, policy evaluation, validation, state management, and reporting.
