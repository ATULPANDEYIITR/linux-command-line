'use strict';

/*
 * Network Virtualization Laboratory
 *
 * Node.js standard-library implementation focused on JavaScript-specific
 * event-driven modeling:
 *   - virtual networks and tenant isolation
 *   - virtual-switch MAC learning
 *   - SDN controller events and flow installation
 *   - asynchronous status-check processing
 *   - VXLAN-like overlay encapsulation
 *   - merge-free policy evaluation and operational telemetry
 *
 * Run with:
 *   node network-virtualization.js
 */

const { EventEmitter } = require('node:events');

const sleep = (milliseconds) =>
    new Promise((resolve) => setTimeout(resolve, milliseconds));

class VirtualNetwork {
    constructor(name, cidr, vni) {
        this.name = name;
        this.cidr = cidr;
        this.vni = vni;
        this.endpoints = new Map();
    }

    addEndpoint(endpoint) {
        if (this.endpoints.has(endpoint.name)) {
            throw new Error(`Endpoint ${endpoint.name} already exists`);
        }

        if (endpoint.vni !== this.vni) {
            throw new Error(
                `Endpoint ${endpoint.name} is mapped to VNI ${endpoint.vni}, ` +
                `expected ${this.vni}`
            );
        }

        this.endpoints.set(endpoint.name, Object.freeze({ ...endpoint }));
    }
}

class VirtualSwitch {
    constructor(name) {
        this.name = name;
        this.ports = new Map();
        this.macTable = new Map();
        this.flowTable = new Map();
    }

    connect(port, destination) {
        if (this.ports.has(port)) {
            throw new Error(`${this.name}:${port} is already connected`);
        }

        this.ports.set(port, destination);
    }

    learn(macAddress, port) {
        this.macTable.set(macAddress, port);
    }

    installFlow(destinationMac, outputPort, priority = 100) {
        if (!this.ports.has(outputPort)) {
            throw new Error(
                `Cannot install flow: ${outputPort} is not a port on ${this.name}`
            );
        }

        this.flowTable.set(destinationMac, {
            destinationMac,
            outputPort,
            priority,
            installedAt: Date.now()
        });
    }

    lookup(destinationMac) {
        return this.flowTable.get(destinationMac)
            ?? this.macTable.get(destinationMac)
            ?? null;
    }

    forward(frame, ingressPort) {
        if (!this.ports.has(ingressPort)) {
            return {
                action: 'DROP',
                reason: 'unknown ingress port'
            };
        }

        this.learn(frame.sourceMac, ingressPort);

        const outputPort = this.lookup(frame.destinationMac);

        if (outputPort && typeof outputPort === 'object') {
            return {
                action: 'FORWARD',
                port: outputPort.outputPort,
                source: 'SDN_FLOW'
            };
        }

        if (outputPort) {
            return {
                action: 'FORWARD',
                port: outputPort,
                source: 'MAC_TABLE'
            };
        }

        return {
            action: 'FLOOD',
            source: 'UNKNOWN_UNICAST'
        };
    }
}

class SdnController extends EventEmitter {
    constructor() {
        super();
        this.switches = new Map();
        this.policy = new Map();
    }

    registerSwitch(virtualSwitch) {
        this.switches.set(virtualSwitch.name, virtualSwitch);
    }

    setTenantPolicy(sourceVni, destinationVni, allowed) {
        this.policy.set(`${sourceVni}:${destinationVni}`, allowed);
    }

    isAllowed(sourceVni, destinationVni) {
        return this.policy.get(`${sourceVni}:${destinationVni}`) === true;
    }

    programFlow(switchName, destinationMac, outputPort) {
        const virtualSwitch = this.switches.get(switchName);

        if (!virtualSwitch) {
            throw new Error(`Unknown switch ${switchName}`);
        }

        virtualSwitch.installFlow(destinationMac, outputPort);
        this.emit('flowInstalled', {
            switchName,
            destinationMac,
            outputPort
        });
    }

    async runStatusChecks(checks) {
        const results = [];

        for (const check of checks) {
            await sleep(check.delayMs);

            const result = {
                name: check.name,
                passed: Boolean(check.passed)
            };

            results.push(result);
            this.emit('statusCheckCompleted', result);
        }

        return results;
    }
}

class OverlayNetwork {
    constructor() {
        this.vtepTable = new Map();
        this.vniTable = new Map();
    }

    registerVtep(switchName, address) {
        this.vtepTable.set(switchName, address);
    }

    registerSegment(segmentName, vni) {
        if (vni < 1 || vni > 0xFFFFFF) {
            throw new Error('VNI must fit in 24 bits');
        }

        this.vniTable.set(segmentName, vni);
    }

    encapsulate(innerFrame, sourceSwitch, destinationSwitch) {
        const vni = this.vniTable.get(innerFrame.segment);
        const sourceVtep = this.vtepTable.get(sourceSwitch);
        const destinationVtep = this.vtepTable.get(destinationSwitch);

        if (vni === undefined) {
            throw new Error(`No VNI for segment ${innerFrame.segment}`);
        }

        if (!sourceVtep || !destinationVtep) {
            throw new Error('Both source and destination VTEPs are required');
        }

        return Object.freeze({
            outer: {
                source: sourceVtep,
                destination: destinationVtep,
                protocol: 'UDP/VXLAN-like'
            },
            vni,
            inner: innerFrame
        });
    }

    decapsulate(overlayFrame, expectedSegment) {
        const expectedVni = this.vniTable.get(expectedSegment);

        if (expectedVni !== overlayFrame.vni) {
            throw new Error('VNI mismatch: refusing cross-segment decapsulation');
        }

        return overlayFrame.inner;
    }
}

class NetworkVirtualizationLab {
    constructor() {
        this.networks = new Map();
        this.switches = new Map();
        this.endpoints = new Map();
        this.controller = new SdnController();
        this.overlay = new OverlayNetwork();

        this.controller.on('flowInstalled', (event) => {
            console.log(
                `[EVENT] flow installed on ${event.switchName}: ` +
                `${event.destinationMac} -> ${event.outputPort}`
            );
        });

        this.controller.on('statusCheckCompleted', (event) => {
            console.log(
                `[EVENT] status check "${event.name}": ` +
                `${event.passed ? 'PASS' : 'FAIL'}`
            );
        });
    }

    addNetwork(network) {
        if (this.networks.has(network.name)) {
            throw new Error(`Network ${network.name} already exists`);
        }

        this.networks.set(network.name, network);
        this.overlay.registerSegment(network.name, network.vni);
    }

    addSwitch(virtualSwitch) {
        this.switches.set(virtualSwitch.name, virtualSwitch);
        this.controller.registerSwitch(virtualSwitch);
    }

    addEndpoint(endpoint) {
        const network = this.networks.get(endpoint.segment);

        if (!network) {
            throw new Error(`Unknown virtual network ${endpoint.segment}`);
        }

        network.addEndpoint(endpoint);
        this.endpoints.set(endpoint.name, endpoint);
    }

    async send(sourceName, destinationName, payload) {
        const source = this.endpoints.get(sourceName);
        const destination = this.endpoints.get(destinationName);

        if (!source || !destination) {
            throw new Error('Both endpoints must exist');
        }

        console.log(`\n${sourceName} -> ${destinationName}`);

        if (!this.controller.isAllowed(source.vni, destination.vni)) {
            console.log('DROP: tenant policy denies the traffic');
            return;
        }

        const frame = {
            sourceMac: source.mac,
            destinationMac: destination.mac,
            sourceIp: source.ip,
            destinationIp: destination.ip,
            segment: source.segment,
            payload
        };

        const virtualSwitch = this.switches.get(source.switchName);
        const forwarding = virtualSwitch.forward(frame, source.port);

        console.log(
            `switch result: ${forwarding.action}` +
            (forwarding.port ? ` via ${forwarding.port}` : '')
        );

        if (forwarding.action === 'FLOOD') {
            console.log(
                'The switch has not learned the destination; ' +
                'an unknown-unicast flood is required.'
            );
        }
    }
}

async function buildAndRun() {
    const lab = new NetworkVirtualizationLab();

    const tenantA = new VirtualNetwork('tenant-a', '10.10.10.0/24', 1010);
    const tenantB = new VirtualNetwork('tenant-b', '10.20.20.0/24', 2020);

    lab.addNetwork(tenantA);
    lab.addNetwork(tenantB);

    const switchA = new VirtualSwitch('vswitch-a');
    const switchB = new VirtualSwitch('vswitch-b');

    switchA.connect('p1', 'web-a');
    switchA.connect('p2', 'db-a');
    switchB.connect('p1', 'web-b');
    switchB.connect('p2', 'db-b');

    lab.addSwitch(switchA);
    lab.addSwitch(switchB);

    lab.overlay.registerVtep('vswitch-a', '192.0.2.10');
    lab.overlay.registerVtep('vswitch-b', '192.0.2.20');

    lab.addEndpoint({
        name: 'web-a',
        mac: '02:00:00:00:00:01',
        ip: '10.10.10.10',
        segment: 'tenant-a',
        vni: 1010,
        switchName: 'vswitch-a',
        port: 'p1'
    });

    lab.addEndpoint({
        name: 'db-a',
        mac: '02:00:00:00:00:02',
        ip: '10.10.10.20',
        segment: 'tenant-a',
        vni: 1010,
        switchName: 'vswitch-a',
        port: 'p2'
    });

    lab.addEndpoint({
        name: 'web-b',
        mac: '02:00:00:00:00:11',
        ip: '10.20.20.10',
        segment: 'tenant-b',
        vni: 2020,
        switchName: 'vswitch-b',
        port: 'p1'
    });

    lab.addEndpoint({
        name: 'db-b',
        mac: '02:00:00:00:00:12',
        ip: '10.20.20.20',
        segment: 'tenant-b',
        vni: 2020,
        switchName: 'vswitch-b',
        port: 'p2'
    });

    lab.controller.setTenantPolicy(1010, 1010, true);
    lab.controller.setTenantPolicy(2020, 2020, true);
    lab.controller.setTenantPolicy(1010, 2020, false);
    lab.controller.setTenantPolicy(2020, 1010, false);

    console.log('=== Virtual network isolation ===');
    await lab.send('web-a', 'db-a', 'HTTP request');
    await lab.send('web-a', 'web-b', 'unauthorized tenant traffic');

    console.log('\n=== SDN flow programming ===');
    lab.controller.programFlow(
        'vswitch-a',
        '02:00:00:00:00:02',
        'p2'
    );
    await lab.send('web-a', 'db-a', 'controller-programmed request');

    console.log('\n=== Asynchronous controller status checks ===');
    const checks = await lab.controller.runStatusChecks([
        { name: 'underlay-reachability', passed: true, delayMs: 20 },
        { name: 'vtep-health', passed: true, delayMs: 20 },
        { name: 'tenant-policy-consistency', passed: true, delayMs: 20 }
    ]);

    if (!checks.every((check) => check.passed)) {
        throw new Error('Overlay deployment blocked by failed status checks');
    }

    console.log('\n=== Overlay encapsulation ===');

    const inner = {
        sourceMac: '02:00:00:00:00:01',
        destinationMac: '02:00:00:00:00:02',
        sourceIp: '10.10.10.10',
        destinationIp: '10.10.10.20',
        segment: 'tenant-a',
        payload: 'database query'
    };

    const overlayFrame = lab.overlay.encapsulate(
        inner,
        'vswitch-a',
        'vswitch-b'
    );

    console.log(
        `outer: ${overlayFrame.outer.source} -> ` +
        `${overlayFrame.outer.destination}`
    );
    console.log(`VNI: ${overlayFrame.vni}`);
    console.log(
        `inner: ${overlayFrame.inner.sourceIp} -> ` +
        `${overlayFrame.inner.destinationIp}`
    );

    const recovered = lab.overlay.decapsulate(overlayFrame, 'tenant-a');
    console.log(`decapsulated segment: ${recovered.segment}`);

    try {
        lab.overlay.decapsulate(overlayFrame, 'tenant-b');
    } catch (error) {
        console.log(`security validation: ${error.message}`);
    }

    console.log('\n=== Virtual switch state ===');
    console.log(
        JSON.stringify(
            {
                macTable: Object.fromEntries(switchA.macTable),
                flowTable: Object.fromEntries(switchA.flowTable)
            },
            null,
            2
        )
    );
}

buildAndRun().catch((error) => {
    console.error(`Fatal error: ${error.message}`);
    process.exitCode = 1;
});
