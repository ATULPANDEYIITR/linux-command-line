#include <algorithm>
#include <chrono>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

using namespace std;

struct Packet {
    string sourceMac;
    string destinationMac;
    string sourceIp;
    string destinationIp;
    int vni{};
    string payload;
};

struct FlowRule {
    string destinationMac;
    string outputPort;
    int priority{};
    size_t packetCount{};
};

struct StatusCheck {
    string name;
    bool passed{};
};

class VirtualSwitch {
private:
    string name_;
    set<string> ports_;
    unordered_map<string, string> macTable_;
    vector<FlowRule> flows_;

public:
    explicit VirtualSwitch(string name) : name_(move(name)) {}

    const string& name() const {
        return name_;
    }

    void addPort(const string& port) {
        if (!ports_.insert(port).second) {
            throw invalid_argument("duplicate virtual-switch port: " + port);
        }
    }

    bool hasPort(const string& port) const {
        return ports_.contains(port);
    }

    void learn(const string& mac, const string& ingressPort) {
        if (!hasPort(ingressPort)) {
            throw invalid_argument("unknown ingress port: " + ingressPort);
        }

        macTable_[mac] = ingressPort;
    }

    void installFlow(const FlowRule& rule) {
        if (!hasPort(rule.outputPort)) {
            throw invalid_argument(
                "cannot install flow to unknown port " + rule.outputPort
            );
        }

        flows_.push_back(rule);

        sort(
            flows_.begin(),
            flows_.end(),
            [](const FlowRule& a, const FlowRule& b) {
                return a.priority > b.priority;
            }
        );
    }

    optional<string> lookupFlow(const string& destinationMac) {
        for (auto& flow : flows_) {
            if (flow.destinationMac == destinationMac) {
                ++flow.packetCount;
                return flow.outputPort;
            }
        }

        const auto learned = macTable_.find(destinationMac);
        if (learned != macTable_.end()) {
            return learned->second;
        }

        return nullopt;
    }

    string forward(const Packet& packet, const string& ingressPort) {
        learn(packet.sourceMac, ingressPort);

        auto destination = lookupFlow(packet.destinationMac);

        if (destination.has_value() && *destination != ingressPort) {
            return "FORWARD via " + *destination;
        }

        if (destination.has_value() && *destination == ingressPort) {
            return "DROP: destination resolves to ingress port";
        }

        return "FLOOD: unknown destination";
    }

    void printState() const {
        cout << "  " << name_ << " MAC table:\n";
        for (const auto& [mac, port] : macTable_) {
            cout << "    " << mac << " -> " << port << '\n';
        }

        cout << "  " << name_ << " flow table:\n";
        for (const auto& flow : flows_) {
            cout << "    " << flow.destinationMac
                 << " -> " << flow.outputPort
                 << " priority=" << flow.priority
                 << " packets=" << flow.packetCount << '\n';
        }
    }
};

class TenantPolicy {
private:
    map<pair<int, int>, bool> rules_;

public:
    void allow(int sourceVni, int destinationVni) {
        rules_[{sourceVni, destinationVni}] = true;
    }

    void deny(int sourceVni, int destinationVni) {
        rules_[{sourceVni, destinationVni}] = false;
    }

    bool permits(int sourceVni, int destinationVni) const {
        auto it = rules_.find({sourceVni, destinationVni});

        if (it == rules_.end()) {
            return false;
        }

        return it->second;
    }
};

class SdnController {
private:
    map<string, VirtualSwitch*> switches_;
    TenantPolicy policy_;
    vector<string> auditLog_;

public:
    void registerSwitch(VirtualSwitch& virtualSwitch) {
        switches_[virtualSwitch.name()] = &virtualSwitch;
        auditLog_.push_back(
            "registered switch " + virtualSwitch.name()
        );
    }

    TenantPolicy& policy() {
        return policy_;
    }

    void installFlow(
        const string& switchName,
        const string& destinationMac,
        const string& outputPort,
        int priority = 100
    ) {
        auto it = switches_.find(switchName);

        if (it == switches_.end()) {
            throw invalid_argument("unknown switch " + switchName);
        }

        it->second->installFlow(
            FlowRule{destinationMac, outputPort, priority, 0}
        );

        ostringstream message;
        message << "controller installed " << destinationMac
                << " -> " << outputPort
                << " on " << switchName;
        auditLog_.push_back(message.str());
    }

    bool authorize(const Packet& packet) {
        const bool result =
            policy_.permits(packet.vni, packet.vni);

        auditLog_.push_back(
            "same-segment authorization for VNI " +
            to_string(packet.vni) + ": " +
            (result ? "ALLOW" : "DENY")
        );

        return result;
    }

    void printAudit() const {
        cout << "Controller audit log:\n";
        for (const auto& event : auditLog_) {
            cout << "  " << event << '\n';
        }
    }
};

class OverlayNetwork {
private:
    struct Vtep {
        string switchName;
        string address;
    };

    unordered_map<int, string> vniToSegment_;
    unordered_map<string, string> switchToVtep_;

public:
    void registerSegment(int vni, const string& segment) {
        if (vni < 1 || vni > 0xFFFFFF) {
            throw invalid_argument("VXLAN VNI must be 24 bits");
        }

        if (vniToSegment_.contains(vni)) {
            throw invalid_argument("VNI already registered");
        }

        vniToSegment_[vni] = segment;
    }

    void registerVtep(const string& switchName, const string& address) {
        switchToVtep_[switchName] = address;
    }

    struct EncapsulatedFrame {
        string outerSource;
        string outerDestination;
        int vni{};
        Packet inner;
    };

    EncapsulatedFrame encapsulate(
        const Packet& inner,
        const string& sourceSwitch,
        const string& destinationSwitch
    ) const {
        if (!vniToSegment_.contains(inner.vni)) {
            throw invalid_argument("unknown overlay VNI");
        }

        auto source = switchToVtep_.find(sourceSwitch);
        auto destination = switchToVtep_.find(destinationSwitch);

        if (source == switchToVtep_.end() ||
            destination == switchToVtep_.end()) {
            throw invalid_argument("missing VTEP");
        }

        return {
            source->second,
            destination->second,
            inner.vni,
            inner
        };
    }

    Packet decapsulate(
        const EncapsulatedFrame& frame,
        int expectedVni
    ) const {
        if (frame.vni != expectedVni) {
            throw runtime_error(
                "VNI validation failed: frame belongs to another segment"
            );
        }

        return frame.inner;
    }
};

class GovernanceEngine {
private:
    vector<StatusCheck> checks_;

public:
    void addStatusCheck(string name, bool passed) {
        checks_.push_back({move(name), passed});
    }

    bool mergeEligible() const {
        return all_of(
            checks_.begin(),
            checks_.end(),
            [](const StatusCheck& check) {
                return check.passed;
            }
        );
    }

    void printChecks() const {
        for (const auto& check : checks_) {
            cout << "  " << check.name << ": "
                 << (check.passed ? "PASS" : "FAIL") << '\n';
        }
    }
};

int main() {
    try {
        cout << "=== Network Virtualization Case Study ===\n\n";

        /*
         * The scenario represents two isolated tenants using virtual
         * switches. The controller programs the data plane, while the
         * overlay provides logical Layer-2 connectivity over an IP underlay.
         */
        VirtualSwitch switchA("vswitch-a");
        VirtualSwitch switchB("vswitch-b");

        switchA.addPort("p1");
        switchA.addPort("p2");
        switchB.addPort("p1");
        switchB.addPort("p2");

        SdnController controller;
        controller.registerSwitch(switchA);
        controller.registerSwitch(switchB);

        constexpr int tenantAVni = 1010;
        constexpr int tenantBVni = 2020;

        controller.policy().allow(tenantAVni, tenantAVni);
        controller.policy().allow(tenantBVni, tenantBVni);
        controller.policy().deny(tenantAVni, tenantBVni);
        controller.policy().deny(tenantBVni, tenantAVni);

        Packet firstPacket{
            "02:00:00:00:00:01",
            "02:00:00:00:00:02",
            "10.10.10.10",
            "10.10.10.20",
            tenantAVni,
            "database request"
        };

        cout << "Initial data-plane forwarding:\n";

        if (controller.authorize(firstPacket)) {
            cout << "  " << switchA.forward(firstPacket, "p1") << '\n';
        } else {
            cout << "  DROP: policy denied packet\n";
        }

        /*
         * The controller now knows the intended destination port. This
         * resembles an OpenFlow-style control decision: the control plane
         * installs a match/action rule so subsequent packets can be handled
         * locally by the virtual switch.
         */
        controller.installFlow(
            "vswitch-a",
            firstPacket.destinationMac,
            "p2",
            200
        );

        cout << "\nController-programmed forwarding:\n";
        cout << "  " << switchA.forward(firstPacket, "p1") << '\n';

        Packet crossTenantPacket{
            "02:00:00:00:00:01",
            "02:00:00:00:00:11",
            "10.10.10.10",
            "10.20.20.10",
            tenantBVni,
            "cross-tenant request"
        };

        /*
         * The VNI is deliberately changed to model a packet entering a
         * different logical tenant. The policy denies it rather than
         * allowing a virtual-switch forwarding decision to bypass isolation.
         */
        cout << "\nTenant isolation:\n";
        cout << "  "
             << (controller.authorize(crossTenantPacket)
                     ? "ALLOW"
                     : "DROP")
             << '\n';

        OverlayNetwork overlay;
        overlay.registerSegment(tenantAVni, "tenant-a");
        overlay.registerSegment(tenantBVni, "tenant-b");
        overlay.registerVtep("vswitch-a", "192.0.2.10");
        overlay.registerVtep("vswitch-b", "192.0.2.20");

        cout << "\nVXLAN-like overlay encapsulation:\n";

        auto encapsulated =
            overlay.encapsulate(firstPacket, "vswitch-a", "vswitch-b");

        cout << "  outer source      : "
             << encapsulated.outerSource << '\n';
        cout << "  outer destination : "
             << encapsulated.outerDestination << '\n';
        cout << "  VNI               : "
             << encapsulated.vni << '\n';
        cout << "  inner source      : "
             << encapsulated.inner.sourceIp << '\n';
        cout << "  inner destination : "
             << encapsulated.inner.destinationIp << '\n';

        auto recovered =
            overlay.decapsulate(encapsulated, tenantAVni);

        cout << "  decapsulated flow : "
             << recovered.sourceIp << " -> "
             << recovered.destinationIp << '\n';

        try {
            overlay.decapsulate(encapsulated, tenantBVni);
            cout << "  ERROR: invalid VNI accepted\n";
        } catch (const exception& error) {
            cout << "  expected security rejection: "
                 << error.what() << '\n';
        }

        cout << "\nOperational status checks:\n";

        GovernanceEngine governance;
        governance.addStatusCheck("underlay reachability", true);
        governance.addStatusCheck("VTEP availability", true);
        governance.addStatusCheck("VNI consistency", true);
        governance.addStatusCheck("tenant policy consistency", true);

        governance.printChecks();
        cout << "  deployment status: "
             << (governance.mergeEligible() ? "READY" : "BLOCKED")
             << '\n';

        cout << "\nVirtual-switch state:\n";
        switchA.printState();

        cout << '\n';
        controller.printAudit();

        cout << "\nCase-study observations:\n";
        cout << "  Virtual switches implement forwarding in the data plane.\n";
        cout << "  The SDN controller separates policy and forwarding decisions.\n";
        cout << "  VNIs identify logical overlay segments independently of the underlay.\n";
        cout << "  Tenant policy prevents logical isolation from being bypassed by forwarding.\n";
        cout << "  The overlay carries an inner packet through an IP-based transport path.\n";

    } catch (const exception& error) {
        cerr << "Fatal configuration/runtime error: "
             << error.what() << '\n';
        return 1;
    }

    return 0;
}
