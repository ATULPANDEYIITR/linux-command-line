"use strict";

/*
 * Cloud Infrastructure Project
 *
 * This Node.js program models a virtual cloud control plane with:
 * - virtual networks and subnets
 * - compute instances
 * - object and block storage
 * - security groups
 * - IAM-style authorization
 * - asynchronous event processing
 *
 * The implementation deliberately uses JavaScript's event-driven model to
 * represent infrastructure events rather than translating the Python design.
 */

const crypto = require("crypto");
const { EventEmitter } = require("events");

const InstanceState = Object.freeze({
  STOPPED: "stopped",
  RUNNING: "running",
  TERMINATED: "terminated",
});

class CloudError extends Error {}

class ValidationError extends CloudError {}

class AuthorizationError extends CloudError {}

class SecurityGroup {
  constructor(name) {
    this.name = name;
    this.inbound = [];
    this.outbound = [];
  }

  addInboundRule({ protocol, port = null, source }) {
    this.inbound.push({ protocol, port, source });
  }

  addOutboundRule({ protocol, port = null, destination }) {
    this.outbound.push({ protocol, port, destination });
  }

  allowsInbound(protocol, port, sourceIp) {
    return this.inbound.some((rule) => {
      const protocolMatches =
        rule.protocol === "all" || rule.protocol === protocol;

      const portMatches = rule.port === null || rule.port === port;

      const sourceMatches =
        rule.source === "0.0.0.0/0" ||
        sourceIp.startsWith(rule.source.split("/")[0].split(".").slice(0, 3).join(".") + ".");

      return protocolMatches && portMatches && sourceMatches;
    });
  }
}

class Subnet {
  constructor(name, cidr, publicSubnet) {
    this.name = name;
    this.cidr = cidr;
    this.publicSubnet = publicSubnet;
  }
}

class VirtualNetwork {
  constructor(name, cidr) {
    this.name = name;
    this.cidr = cidr;
    this.subnets = new Map();
  }

  addSubnet(subnet) {
    if (this.subnets.has(subnet.name)) {
      throw new ValidationError(`Subnet already exists: ${subnet.name}`);
    }

    this.subnets.set(subnet.name, subnet);
  }
}

class ComputeInstance {
  constructor({
    id,
    name,
    subnet,
    privateIp,
    securityGroup,
  }) {
    this.id = id;
    this.name = name;
    this.subnet = subnet;
    this.privateIp = privateIp;
    this.securityGroup = securityGroup;
    this.state = InstanceState.STOPPED;
    this.volumes = new Set();
  }

  start() {
    if (this.state === InstanceState.TERMINATED) {
      throw new ValidationError("Terminated instances cannot be started");
    }

    this.state = InstanceState.RUNNING;
  }

  stop() {
    if (this.state === InstanceState.TERMINATED) {
      throw new ValidationError("Terminated instances cannot be stopped");
    }

    this.state = InstanceState.STOPPED;
  }

  terminate() {
    this.state = InstanceState.TERMINATED;
  }
}

class ObjectBucket {
  constructor(name, encryptionRequired = true) {
    this.name = name;
    this.encryptionRequired = encryptionRequired;
    this.objects = new Map();
  }

  put(key, value, { encrypted = true } = {}) {
    if (!key || !key.trim()) {
      throw new ValidationError("Object key cannot be empty");
    }

    if (this.encryptionRequired && !encrypted) {
      throw new AuthorizationError(
        "The bucket requires encrypted object storage"
      );
    }

    const content = Buffer.isBuffer(value)
      ? value
      : Buffer.from(String(value));

    const checksum = crypto
      .createHash("sha256")
      .update(content)
      .digest("hex");

    this.objects.set(key, {
      content,
      checksum,
      encrypted,
    });
  }

  get(key) {
    const object = this.objects.get(key);

    if (!object) {
      throw new ValidationError(`Object not found: ${key}`);
    }

    return object.content;
  }
}

class BlockVolume {
  constructor(name, sizeGb) {
    if (!Number.isInteger(sizeGb) || sizeGb <= 0) {
      throw new ValidationError("Block volume size must be positive");
    }

    this.name = name;
    this.sizeGb = sizeGb;
    this.encrypted = true;
    this.attachedInstance = null;
  }

  attach(instanceId) {
    if (this.attachedInstance !== null) {
      throw new ValidationError(
        `Volume ${this.name} is already attached`
      );
    }

    this.attachedInstance = instanceId;
  }
}

class IAM {
  constructor() {
    this.users = new Map();

    this.permissions = new Map([
      [
        "administrator",
        new Set(["compute", "network", "storage", "security"]),
      ],
      ["developer", new Set(["compute", "storage"])],
      ["network-admin", new Set(["network", "security"])],
      ["auditor", new Set(["storage-read"])],
    ]);
  }

  addUser(username, roles) {
    if (this.users.has(username)) {
      throw new ValidationError(`User already exists: ${username}`);
    }

    this.users.set(username, new Set(roles));
  }

  can(username, resource, action) {
    const roles = this.users.get(username);

    if (!roles) {
      return false;
    }

    for (const role of roles) {
      const permissions = this.permissions.get(role) || new Set();

      if (permissions.has(resource)) {
        return true;
      }

      if (
        resource === "storage" &&
        action === "read" &&
        permissions.has("storage-read")
      ) {
        return true;
      }
    }

    return false;
  }
}

class CloudControlPlane extends EventEmitter {
  constructor() {
    super();

    this.networks = new Map();
    this.securityGroups = new Map();
    this.instances = new Map();
    this.buckets = new Map();
    this.volumes = new Map();
    this.iam = new IAM();

    this.on("instance.started", ({ instance }) => {
      console.log(`[event] ${instance.id} entered RUNNING state`);
    });

    this.on("volume.attached", ({ volume, instance }) => {
      console.log(
        `[event] ${volume.name} attached to ${instance.id}`
      );
    });
  }

  createNetwork(name, cidr) {
    if (this.networks.has(name)) {
      throw new ValidationError(`Network already exists: ${name}`);
    }

    const network = new VirtualNetwork(name, cidr);
    this.networks.set(name, network);
    return network;
  }

  createSecurityGroup(name) {
    if (this.securityGroups.has(name)) {
      throw new ValidationError(`Security group already exists: ${name}`);
    }

    const group = new SecurityGroup(name);
    this.securityGroups.set(name, group);
    return group;
  }

  createInstance(config) {
    if (this.instances.has(config.id)) {
      throw new ValidationError(`Instance already exists: ${config.id}`);
    }

    if (!this.networks.values().next().value) {
      throw new ValidationError("A network must exist before compute");
    }

    if (!this.securityGroups.has(config.securityGroup)) {
      throw new ValidationError(
        `Unknown security group: ${config.securityGroup}`
      );
    }

    const instance = new ComputeInstance(config);
    this.instances.set(instance.id, instance);

    return instance;
  }

  startInstance(id) {
    const instance = this.instances.get(id);

    if (!instance) {
      throw new ValidationError(`Unknown instance: ${id}`);
    }

    instance.start();
    this.emit("instance.started", { instance });

    return instance;
  }

  createBucket(name) {
    if (this.buckets.has(name)) {
      throw new ValidationError(`Bucket already exists: ${name}`);
    }

    const bucket = new ObjectBucket(name);
    this.buckets.set(name, bucket);

    return bucket;
  }

  createVolume(name, sizeGb) {
    if (this.volumes.has(name)) {
      throw new ValidationError(`Volume already exists: ${name}`);
    }

    const volume = new BlockVolume(name, sizeGb);
    this.volumes.set(name, volume);

    return volume;
  }

  attachVolume(volumeName, instanceId) {
    const volume = this.volumes.get(volumeName);
    const instance = this.instances.get(instanceId);

    if (!volume || !instance) {
      throw new ValidationError("Volume or instance does not exist");
    }

    if (instance.state === InstanceState.TERMINATED) {
      throw new ValidationError(
        "Terminated instances cannot receive volumes"
      );
    }

    volume.attach(instanceId);
    instance.volumes.add(volumeName);

    this.emit("volume.attached", { volume, instance });
  }

  canConnect(sourceId, destinationId, protocol, port) {
    const source = this.instances.get(sourceId);
    const destination = this.instances.get(destinationId);

    if (!source || !destination) {
      throw new ValidationError("Source or destination instance not found");
    }

    if (
      source.state !== InstanceState.RUNNING ||
      destination.state !== InstanceState.RUNNING
    ) {
      return false;
    }

    const group = this.securityGroups.get(destination.securityGroup);

    return group.allowsInbound(
      protocol,
      port,
      source.privateIp
    );
  }
}

function wait(milliseconds) {
  return new Promise((resolve) => {
    setTimeout(resolve, milliseconds);
  });
}

async function provisionInfrastructure() {
  const cloud = new CloudControlPlane();

  console.log("=== Cloud Infrastructure Control Plane ===");

  const network = cloud.createNetwork(
    "production-vpc",
    "10.0.0.0/16"
  );

  network.addSubnet(
    new Subnet("public-web", "10.0.1.0/24", true)
  );

  network.addSubnet(
    new Subnet("private-app", "10.0.10.0/24", false)
  );

  network.addSubnet(
    new Subnet("private-db", "10.0.20.0/24", false)
  );

  const webGroup = cloud.createSecurityGroup("web-sg");

  webGroup.addInboundRule({
    protocol: "tcp",
    port: 443,
    source: "0.0.0.0/0",
  });

  webGroup.addInboundRule({
    protocol: "tcp",
    port: 22,
    source: "10.0.10.0/24",
  });

  const databaseGroup =
    cloud.createSecurityGroup("database-sg");

  databaseGroup.addInboundRule({
    protocol: "tcp",
    port: 5432,
    source: "10.0.10.0/24",
  });

  cloud.iam.addUser("platform-admin", ["administrator"]);
  cloud.iam.addUser("application-developer", ["developer"]);
  cloud.iam.addUser("auditor", ["auditor"]);

  const web = cloud.createInstance({
    id: "web-01",
    name: "web-server",
    subnet: "public-web",
    privateIp: "10.0.1.10",
    securityGroup: "web-sg",
  });

  const app = cloud.createInstance({
    id: "app-01",
    name: "application-server",
    subnet: "private-app",
    privateIp: "10.0.10.10",
    securityGroup: "web-sg",
  });

  const database = cloud.createInstance({
    id: "db-01",
    name: "database-server",
    subnet: "private-db",
    privateIp: "10.0.20.10",
    securityGroup: "database-sg",
  });

  cloud.startInstance(web.id);
  await wait(50);
  cloud.startInstance(app.id);
  await wait(50);
  cloud.startInstance(database.id);

  const bucket = cloud.createBucket(
    "production-artifacts"
  );

  bucket.put(
    "config/app.json",
    JSON.stringify({
      environment: "production",
      database: "private-db",
    }),
    { encrypted: true }
  );

  const volume = cloud.createVolume(
    "database-data",
    100
  );

  cloud.attachVolume(volume.name, database.id);

  console.log(
    "Application -> database PostgreSQL:",
    cloud.canConnect(
      app.id,
      database.id,
      "tcp",
      5432
    )
  );

  console.log(
    "Public web -> database PostgreSQL:",
    cloud.canConnect(
      web.id,
      database.id,
      "tcp",
      5432
    )
  );

  console.log(
    "Developer can modify network:",
    cloud.iam.can(
      "application-developer",
      "network",
      "write"
    )
  );

  console.log(
    "Auditor can read storage:",
    cloud.iam.can(
      "auditor",
      "storage",
      "read"
    )
  );

  console.log(
    "Stored configuration:",
    bucket.get("config/app.json").toString()
  );

  try {
    bucket.put(
      "unsafe.txt",
      "plaintext",
      { encrypted: false }
    );
  } catch (error) {
    console.log(
      "Storage security policy blocked write:",
      error.message
    );
  }

  try {
    cloud.attachVolume("database-data", web.id);
  } catch (error) {
    console.log(
      "Volume lifecycle validation:",
      error.message
    );
  }

  return cloud;
}

provisionInfrastructure()
  .then(() => {
    console.log("Infrastructure provisioning simulation completed.");
  })
  .catch((error) => {
    console.error("Provisioning failed:", error.message);
    process.exitCode = 1;
  });
