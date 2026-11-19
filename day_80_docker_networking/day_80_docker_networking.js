"use strict";

/*
 * Docker Networking: Event-driven network topology and policy engine.
 *
 * Models:
 * - User-defined bridge networks
 * - Network-scoped service discovery
 * - Host networking
 * - Container networking
 * - Port publishing
 * - Internal network isolation
 * - Asynchronous connectivity evaluation
 *
 * Runtime: Node.js 18+
 * Dependencies: Node.js standard library only.
 */

const { EventEmitter } = require("node:events");
const net = require("node:net");

class NetworkError extends Error {
    constructor(message, code = "NETWORK_ERROR") {
        super(message);
        this.name = "NetworkError";
        this.code = code;
    }
}

const NetworkMode = Object.freeze({
    BRIDGE: "bridge",
    HOST: "host",
    NONE: "none"
});

class NetworkSegment {
    constructor({
        name,
        subnet,
        gateway,
        internal = false
    }) {
        if (!name || !net.isIP(subnet.split("/")[0])) {
            throw new NetworkError("Invalid network configuration.");
        }

        const [base, prefixText] = subnet.split("/");
        const prefix = Number(prefixText);

        if (
            !Number.isInteger(prefix)
            || prefix < 16
            || prefix > 29
            || net.isIP(base) !== 4
        ) {
            throw new NetworkError("Invalid IPv4 subnet.");
        }

        this.name = name;
        this.subnet = subnet;
        this.internal = Boolean(internal);
        this.gateway = gateway || base;
        this.members = new Set();
        this.addresses = new Map();

        if (net.isIP(this.gateway) !== 4) {
            throw new NetworkError("Invalid gateway.");
        }

        const [baseNumber, mask] = [
            NetworkSegment.ipToNumber(base),
            (0xFFFFFFFF << (32 - prefix)) >>> 0
        ];

        this.networkAddress = (baseNumber & mask) >>> 0;
        this.broadcastAddress =
            (this.networkAddress | (~mask >>> 0)) >>> 0;

        const gatewayNumber = NetworkSegment.ipToNumber(this.gateway);

        if (
            gatewayNumber < this.networkAddress
            || gatewayNumber > this.broadcastAddress
        ) {
            throw new NetworkError("Gateway is outside subnet.");
        }

        this.mask = mask;
    }

    static ipToNumber(address) {
        if (net.isIP(address) !== 4) {
            throw new NetworkError("Expected IPv4 address.");
        }

        return address.split(".")
            .reduce((value, octet) =>
                ((value << 8) | Number(octet)) >>> 0, 0);
    }

    allocate() {
        const gatewayNumber = NetworkSegment.ipToNumber(this.gateway);

        for (
            let current = this.networkAddress + 1;
            current < this.broadcastAddress;
            current++
        ) {
            if (
                current !== gatewayNumber
                && !this.addresses.has(current)
            ) {
                const address = [
                    (current >>> 24) & 255,
                    (current >>> 16) & 255,
                    (current >>> 8) & 255,
                    current & 255
                ].join(".");

                return { current, address };
            }
        }

        throw new NetworkError("Subnet address pool exhausted.");
    }

    attach(container) {
        if (this.members.has(container.name)) {
            throw new NetworkError("Duplicate network membership.");
        }

        const allocation = this.allocate();

        this.members.add(container.name);
        this.addresses.set(allocation.current, container.name);

        container.networks.set(this.name, allocation.address);

        return allocation.address;
    }

    detach(container) {
        const address = container.networks.get(this.name);

        if (!address) {
            throw new NetworkError("Container is not attached.");
        }

        this.members.delete(container.name);
        this.addresses.delete(
            NetworkSegment.ipToNumber(address)
        );

        container.networks.delete(this.name);
    }
}

class ContainerService {
    constructor({
        id,
        name,
        image,
        mode = NetworkMode.BRIDGE,
        ports = []
    }) {
        if (!id || !name || !image) {
            throw new NetworkError(
                "Container ID, name, and image are required."
            );
        }

        if (!Object.values(NetworkMode).includes(mode)) {
            throw new NetworkError("Unsupported network mode.");
        }

        this.id = id;
        this.name = name;
        this.image = image;
        this.mode = mode;
        this.ports = new Set(ports);
        this.networks = new Map();
        this.running = true;

        for (const port of this.ports) {
            ContainerService.validatePort(port);
        }
    }

    static validatePort(port) {
        if (
            !Number.isInteger(port)
            || port < 1
            || port > 65535
        ) {
            throw new NetworkError(`Invalid port: ${port}`);
        }
    }
}

class DockerNetworkController extends EventEmitter {
    constructor() {
        super();

        this.networks = new Map();
        this.containers = new Map();
        this.portMappings = new Map();
        this.operationQueue = Promise.resolve();
    }

    _emit(event, payload) {
        this.emit(event, Object.freeze({
            timestamp: new Date().toISOString(),
            ...payload
        }));
    }

    _serialize(operation) {
        // Prevent concurrent topology mutations from allocating
        // the same address or host port.
        const result = this.operationQueue.then(operation);

        this.operationQueue = result.catch(() => {});

        return result;
    }

    async createNetwork(configuration) {
        return this._serialize(async () => {
            const network = new NetworkSegment(configuration);

            if (this.networks.has(network.name)) {
                throw new NetworkError("Network already exists.");
            }

            for (const existing of this.networks.values()) {
                if (
                    existing.networkAddress === network.networkAddress
                    && existing.mask === network.mask
                ) {
                    throw new NetworkError("Duplicate network range.");
                }

                const overlaps =
                    network.networkAddress <= existing.broadcastAddress
                    && existing.networkAddress <= network.broadcastAddress;

                if (overlaps) {
                    throw new NetworkError("Overlapping subnets.");
                }
            }

            this.networks.set(network.name, network);

            this._emit("network.created", {
                network: network.name,
                subnet: network.subnet
            });

            return network;
        });
    }

    async createContainer(configuration) {
        return this._serialize(async () => {
            const container = new ContainerService(configuration);

            if (this.containers.has(container.name)) {
                throw new NetworkError("Container already exists.");
            }

            if (
                container.mode === NetworkMode.BRIDGE
                && !configuration.network
            ) {
                throw new NetworkError(
                    "Bridge mode requires a network."
                );
            }

            if (
                container.mode !== NetworkMode.BRIDGE
                && configuration.network
            ) {
                throw new NetworkError(
                    "Host and none modes cannot join bridge networks."
                );
            }

            if (configuration.network) {
                const network = this.networks.get(configuration.network);

                if (!network) {
                    throw new NetworkError("Network not found.");
                }

                network.attach(container);
            }

            this.containers.set(container.name, container);

            this._emit("container.created", {
                container: container.name,
                mode: container.mode
            });

            return container;
        });
    }

    async connect(containerName, networkName) {
        return this._serialize(async () => {
            const container = this._getRunningContainer(containerName);
            const network = this.networks.get(networkName);

            if (!network) {
                throw new NetworkError("Network not found.");
            }

            if (container.mode !== NetworkMode.BRIDGE) {
                throw new NetworkError(
                    "Only bridge containers can join user networks."
                );
            }

            const address = network.attach(container);

            this._emit("container.connected", {
                container: containerName,
                network: networkName,
                address
            });

            return address;
        });
    }

    _getRunningContainer(name) {
        const container = this.containers.get(name);

        if (!container) {
            throw new NetworkError(
                `Unknown container: ${name}`,
                "CONTAINER_NOT_FOUND"
            );
        }

        if (!container.running) {
            throw new NetworkError(
                `Container is stopped: ${name}`,
                "CONTAINER_STOPPED"
            );
        }

        return container;
    }

    async resolve(sourceName, serviceName, networkName) {
        const source = this._getRunningContainer(sourceName);
        const target = this._getRunningContainer(serviceName);
        const network = this.networks.get(networkName);

        if (!network) {
            throw new NetworkError("Network not found.");
        }

        if (
            !source.networks.has(networkName)
            || !target.networks.has(networkName)
        ) {
            throw new NetworkError(
                "DNS resolution denied: no shared network."
            );
        }

        const address = target.networks.get(networkName);

        this._emit("dns.resolved", {
            source: sourceName,
            target: serviceName,
            address
        });

        return address;
    }

    async evaluateConnection(sourceName, targetName, port) {
        return this._serialize(async () => {
            ContainerService.validatePort(port);

            const source = this._getRunningContainer(sourceName);
            const target = this._getRunningContainer(targetName);

            let allowed = false;
            let reason = "No permitted network path.";

            if (sourceName === targetName) {
                allowed = true;
                reason = "Same container.";
            } else if (
                source.mode === NetworkMode.NONE
                || target.mode === NetworkMode.NONE
            ) {
                reason = "None network mode.";
            } else if (
                source.mode === NetworkMode.HOST
                && target.mode === NetworkMode.HOST
            ) {
                allowed = true;
                reason = "Shared host network namespace.";
            } else if (
                source.mode === NetworkMode.BRIDGE
                && target.mode === NetworkMode.BRIDGE
            ) {
                const shared = [...source.networks.keys()]
                    .filter(name => target.networks.has(name));

                allowed = shared.length > 0
                    && target.ports.has(port);

                reason = allowed
                    ? `Shared network: ${shared.join(", ")}`
                    : "No shared network or destination port.";
            }

            const decision = Object.freeze({
                source: sourceName,
                target: targetName,
                port,
                allowed,
                reason
            });

            this._emit("connection.evaluated", decision);

            return decision;
        });
    }

    async publishPort({
        containerName,
        hostPort,
        containerPort,
        hostIP = "0.0.0.0",
        protocol = "tcp"
    }) {
        return this._serialize(async () => {
            const container = this._getRunningContainer(containerName);

            ContainerService.validatePort(hostPort);
            ContainerService.validatePort(containerPort);

            if (!["tcp", "udp"].includes(protocol)) {
                throw new NetworkError("Unsupported protocol.");
            }

            if (net.isIP(hostIP) !== 4) {
                throw new NetworkError("Invalid host IPv4 address.");
            }

            if (container.mode !== NetworkMode.BRIDGE) {
                throw new NetworkError(
                    "Port publishing requires bridge networking."
                );
            }

            if (!container.ports.has(containerPort)) {
                throw new NetworkError(
                    "Container port is not declared."
                );
            }

            const mappings = [...this.portMappings.values()];

            const conflict = mappings.some(mapping =>
                mapping.hostPort === hostPort
                && mapping.protocol === protocol
                && (
                    mapping.hostIP === "0.0.0.0"
                    || hostIP === "0.0.0.0"
                    || mapping.hostIP === hostIP
                )
            );

            if (conflict) {
                throw new NetworkError("Host port conflict.");
            }

            const key = `${hostIP}:${hostPort}/${protocol}`;

            const mapping = Object.freeze({
                containerName,
                hostIP,
                hostPort,
                containerPort,
                protocol
            });

            this.portMappings.set(key, mapping);

            this._emit("port.published", mapping);

            return mapping;
        });
    }

    async externalAccess(hostPort, containerPort, protocol = "tcp") {
        return this._serialize(async () => {
            ContainerService.validatePort(hostPort);
            ContainerService.validatePort(containerPort);

            return [...this.portMappings.values()].some(mapping => {
                const container = this.containers.get(
                    mapping.containerName
                );

                return (
                    mapping.hostPort === hostPort
                    && mapping.containerPort === containerPort
                    && mapping.protocol === protocol
                    && container
                    && container.running
                );
            });
        });
    }

    async stopContainer(name) {
        return this._serialize(async () => {
            const container = this._getRunningContainer(name);

            container.running = false;

            for (const mapping of [...this.portMappings.entries()]) {
                if (mapping[1].containerName === name) {
                    this.portMappings.delete(mapping[0]);
                }
            }

            this._emit("container.stopped", { container: name });
        });
    }

    inspect(name) {
        const container = this._getRunningContainer(name);

        return {
            id: container.id,
            name: container.name,
            image: container.image,
            mode: container.mode,
            running: container.running,
            networks: Object.fromEntries(container.networks),
            ports: [...container.ports]
        };
    }

    report() {
        return {
            networks: [...this.networks.values()].map(network => ({
                name: network.name,
                subnet: network.subnet,
                internal: network.internal,
                members: [...network.members]
            })),
            containers: [...this.containers.keys()],
            publishedPorts: [...this.portMappings.values()]
        };
    }
}

async function main() {
    const docker = new DockerNetworkController();

    docker.on("network.created", event => {
        console.log("[NETWORK]", event);
    });

    docker.on("connection.evaluated", event => {
        console.log("[POLICY]", event);
    });

    docker.on("port.published", event => {
        console.log("[PORT]", event);
    });

    await docker.createNetwork({
        name: "frontend-net",
        subnet: "172.20.0.0/24"
    });

    await docker.createNetwork({
        name: "backend-net",
        subnet: "172.21.0.0/24",
        internal: true
    });

    await docker.createContainer({
        id: "c101",
        name: "frontend",
        image: "nginx:stable",
        network: "frontend-net",
        ports: [80]
    });

    await docker.createContainer({
        id: "c102",
        name: "api",
        image: "node:22-alpine",
        network: "frontend-net",
        ports: [8000]
    });

    await docker.connect("api", "backend-net");

    await docker.createContainer({
        id: "c103",
        name: "database",
        image: "postgres:18",
        network: "backend-net",
        ports: [5432]
    });

    const databaseIP = await docker.resolve(
        "api",
        "database",
        "backend-net"
    );

    console.log("\nDATABASE DNS:", databaseIP);

    const decisions = await Promise.all([
        docker.evaluateConnection("frontend", "api", 8000),
        docker.evaluateConnection("api", "database", 5432),
        docker.evaluateConnection("frontend", "database", 5432)
    ]);

    console.log("\nCONNECTION RESULTS");
    console.table(decisions);

    await docker.publishPort({
        containerName: "frontend",
        hostIP: "127.0.0.1",
        hostPort: 8080,
        containerPort: 80
    });

    const reachable = await docker.externalAccess(8080, 80);

    console.log("\nEXTERNAL ACCESS:", reachable);

    console.log("\nTOPOLOGY");
    console.log(JSON.stringify(docker.report(), null, 2));

    if (
        !decisions[0].allowed
        || !decisions[1].allowed
        || decisions[2].allowed
        || !reachable
    ) {
        throw new Error("Networking validation failed.");
    }

    console.log("\nALL NETWORK TESTS PASSED");
}

main().catch(error => {
    console.error("NETWORK FAILURE:", error.message);
    process.exitCode = 1;
});
