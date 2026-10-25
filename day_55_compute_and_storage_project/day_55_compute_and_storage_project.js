"use strict";

/**
 * Event-driven compute and storage architecture simulator.
 * Run with Node.js 18 or later.
 */

const crypto = require("node:crypto");
const fs = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const { EventEmitter } = require("node:events");

class ArchitectureError extends Error {}
class ValidationError extends ArchitectureError {}
class CapacityError extends ArchitectureError {}
class IntegrityError extends ArchitectureError {}

const InstanceState = Object.freeze({
  RUNNING: "running",
  STOPPED: "stopped",
  UNHEALTHY: "unhealthy",
});

const BackupState = Object.freeze({
  COMPLETED: "completed",
  FAILED: "failed",
});

function sha256(buffer) {
  return crypto.createHash("sha256").update(buffer).digest("hex");
}

function canonicalJSON(value) {
  if (Array.isArray(value)) {
    return `[${value.map(canonicalJSON).join(",")}]`;
  }
  if (value && typeof value === "object") {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalJSON(value[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

function validateObjectKey(key) {
  if (
    typeof key !== "string" ||
    key.length === 0 ||
    key.startsWith("/") ||
    key.includes("\\") ||
    key.split("/").some((part) => part === ".." || part === "")
  ) {
    throw new ValidationError("Object key must be a safe relative path.");
  }
}

class ObjectStore extends EventEmitter {
  #objects = new Map();

  constructor({ maxObjectBytes = 10_000_000 } = {}) {
    super();
    if (!Number.isSafeInteger(maxObjectBytes) || maxObjectBytes < 1) {
      throw new ValidationError("Invalid object size limit.");
    }
    this.maxObjectBytes = maxObjectBytes;
  }

  put(key, content) {
    validateObjectKey(key);
    if (!Buffer.isBuffer(content)) {
      throw new ValidationError("Content must be a Buffer.");
    }
    if (content.length > this.maxObjectBytes) {
      throw new ValidationError("Object exceeds size limit.");
    }

    const history = this.#objects.get(key) ?? [];
    const object = Object.freeze({
      key,
      version: history.length + 1,
      content: Buffer.from(content),
      checksum: sha256(content),
      deleted: false,
      createdAt: new Date().toISOString(),
    });

    this.#objects.set(key, [...history, object]);
    this.emit("object:stored", {
      key,
      version: object.version,
      checksum: object.checksum,
    });
    return object;
  }

  get(key, version = undefined) {
    const history = this.#objects.get(key) ?? [];
    const object =
      version === undefined
        ? [...history].reverse().find((item) => !item.deleted)
        : history.find((item) => item.version === version);

    if (!object || object.deleted) {
      throw new ArchitectureError(`Object version unavailable: ${key}`);
    }
    return { ...object, content: Buffer.from(object.content) };
  }

  delete(key) {
    const object = this.get(key);
    const history = this.#objects.get(key);
    const tombstone = Object.freeze({
      ...object,
      content: Buffer.from(object.content),
      deleted: true,
      createdAt: new Date().toISOString(),
    });

    // A tombstone preserves history without exposing the deleted version as current.
    this.#objects.set(key, [...history.slice(0, -1), tombstone]);
    this.emit("object:deleted", { key, version: object.version });
  }

  snapshot() {
    const manifest = {};
    const data = {};

    for (const [key, history] of this.#objects) {
      const object = [...history].reverse().find((item) => !item.deleted);
      if (object) {
        manifest[key] = object.version;
        data[key] = object.content.toString("base64");
      }
    }

    return { manifest, data };
  }

  restore(backup) {
    if (backup.state !== BackupState.COMPLETED) {
      throw new IntegrityError("Cannot restore an incomplete backup.");
    }

    const payload = {
      manifest: backup.manifest,
      data: backup.data,
    };
    if (sha256(Buffer.from(canonicalJSON(payload))) !== backup.checksum) {
      throw new IntegrityError("Backup checksum mismatch.");
    }

    if (
      Object.keys(backup.manifest).length !== Object.keys(backup.data).length ||
      Object.keys(backup.manifest).some((key) => !(key in backup.data))
    ) {
      throw new IntegrityError("Backup manifest and data do not match.");
    }

    const replacement = new Map();

    for (const [key, version] of Object.entries(backup.manifest)) {
      validateObjectKey(key);
      if (!Number.isSafeInteger(version) || version < 1) {
        throw new IntegrityError("Invalid backup version.");
      }

      const content = Buffer.from(backup.data[key], "base64");
      if (content.length > this.maxObjectBytes) {
        throw new IntegrityError("Backup object exceeds the configured limit.");
      }

      replacement.set(key, [
        Object.freeze({
          key,
          version,
          content,
          checksum: sha256(content),
          deleted: false,
          createdAt: backup.createdAt,
        }),
      ]);
    }

    this.#objects = replacement;
    this.emit("backup:restored", { backupId: backup.id });
  }
}

class BackupService {
  static create(store) {
    const snapshot = store.snapshot();
    const payload = {
      manifest: snapshot.manifest,
      data: snapshot.data,
    };

    return Object.freeze({
      id: crypto.randomUUID(),
      createdAt: new Date().toISOString(),
      ...snapshot,
      state: BackupState.COMPLETED,
      checksum: sha256(Buffer.from(canonicalJSON(payload))),
    });
  }

  static async writeReport(backup, destination) {
    const directory = await fs.mkdtemp(path.join(os.tmpdir(), "architecture-"));
    const temporaryFile = path.join(directory, "backup-report.json");

    try {
      await fs.writeFile(
        temporaryFile,
        JSON.stringify(
          {
            id: backup.id,
            createdAt: backup.createdAt,
            state: backup.state,
            checksum: backup.checksum,
            objectCount: Object.keys(backup.manifest).length,
          },
          null,
          2
        ),
        { encoding: "utf8", flag: "wx", mode: 0o600 }
      );

      await fs.copyFile(temporaryFile, destination);
    } finally {
      await fs.rm(directory, { recursive: true, force: true });
    }
  }
}

class ComputePool extends EventEmitter {
  #instances = new Map();

  constructor(instances) {
    super();
    for (const instance of instances) {
      if (
        !instance.id ||
        !instance.zone ||
        !Number.isSafeInteger(instance.capacity) ||
        instance.capacity < 1
      ) {
        throw new ValidationError("Invalid compute instance configuration.");
      }
      if (this.#instances.has(instance.id)) {
        throw new ValidationError(`Duplicate instance: ${instance.id}`);
      }

      this.#instances.set(instance.id, {
        ...instance,
        state: InstanceState.RUNNING,
        active: 0,
      });
    }
  }

  acquire() {
    const eligible = [...this.#instances.values()].filter(
      (instance) =>
        instance.state === InstanceState.RUNNING &&
        instance.active < instance.capacity
    );

    eligible.sort(
      (a, b) =>
        a.active / a.capacity - b.active / b.capacity ||
        a.id.localeCompare(b.id)
    );

    if (eligible.length === 0) {
      this.emit("capacity:exhausted");
      throw new CapacityError("No healthy instance has available capacity.");
    }

    const selected = eligible[0];
    selected.active += 1;
    this.emit("request:routed", {
      instanceId: selected.id,
      active: selected.active,
    });
    return selected.id;
  }

  release(id) {
    const instance = this.#instances.get(id);
    if (!instance) throw new ValidationError(`Unknown instance: ${id}`);
    if (instance.active === 0) {
      throw new ValidationError("No connection is available to release.");
    }
    instance.active -= 1;
  }

  setHealth(id, healthy) {
    const instance = this.#instances.get(id);
    if (!instance) throw new ValidationError(`Unknown instance: ${id}`);

    instance.state = healthy
      ? InstanceState.RUNNING
      : InstanceState.UNHEALTHY;

    this.emit("health:changed", {
      instanceId: id,
      state: instance.state,
    });
  }

  report() {
    return [...this.#instances.values()].map((instance) => ({ ...instance }));
  }
}

class ArchitecturePolicy {
  constructor({
    minimumZones = 2,
    minimumRunningInstances = 1,
    requireCompletedBackup = true,
  } = {}) {
    this.minimumZones = minimumZones;
    this.minimumRunningInstances = minimumRunningInstances;
    this.requireCompletedBackup = requireCompletedBackup;
  }

  evaluate(instances, backups) {
    const running = instances.filter(
      (instance) => instance.state === InstanceState.RUNNING
    );
    const errors = [];

    if (new Set(running.map((instance) => instance.zone)).size < this.minimumZones) {
      errors.push("Insufficient zone diversity.");
    }
    if (running.length < this.minimumRunningInstances) {
      errors.push("Insufficient running compute capacity.");
    }
    if (
      this.requireCompletedBackup &&
      !backups.some((backup) => backup.state === BackupState.COMPLETED)
    ) {
      errors.push("No completed backup is available.");
    }

    return { eligible: errors.length === 0, errors };
  }
}

async function handleRequest(pool, store, requestId) {
  const instanceId = pool.acquire();

  try {
    const configuration = store.get("config/service.json");
    await Promise.resolve();

    return {
      requestId,
      instanceId,
      checksum: configuration.checksum,
      status: "served",
    };
  } finally {
    pool.release(instanceId);
  }
}

async function main() {
  const store = new ObjectStore({ maxObjectBytes: 4096 });

  store.on("object:stored", (event) => {
    console.log(`Stored ${event.key}@${event.version}`);
  });
  store.on("capacity:exhausted", () => {
    console.error("Capacity alert: all instances are unavailable.");
  });

  store.put(
    "config/service.json",
    Buffer.from(JSON.stringify({ service: "inventory", revision: 1 }))
  );
  store.put("reports/daily.txt", Buffer.from("Inventory report"));

  const backup = BackupService.create(store);

  const pool = new ComputePool([
    { id: "vm-a", zone: "zone-a", capacity: 2 },
    { id: "vm-b", zone: "zone-b", capacity: 3 },
    { id: "vm-c", zone: "zone-c", capacity: 1 },
  ]);

  const policy = new ArchitecturePolicy();
  const evaluation = policy.evaluate(pool.report(), [backup]);

  if (!evaluation.eligible) {
    throw new ArchitectureError(evaluation.errors.join("; "));
  }

  const responses = await Promise.all(
    Array.from({ length: 8 }, (_, index) =>
      handleRequest(pool, store, `request-${index + 1}`)
    )
  );

  console.log("Request distribution:");
  console.log(
    JSON.stringify(
      responses.reduce((counts, response) => {
        counts[response.instanceId] = (counts[response.instanceId] ?? 0) + 1;
        return counts;
      }, {}),
      null,
      2
    )
  );

  const firstVersion = store.get("config/service.json", 1);
  store.put(
    "config/service.json",
    Buffer.from(JSON.stringify({ service: "inventory", revision: 2 }))
  );

  if (store.get("config/service.json", 1).checksum !== firstVersion.checksum) {
    throw new IntegrityError("Object version history was not preserved.");
  }

  store.delete("reports/daily.txt");
  try {
    store.get("reports/daily.txt");
  } catch (error) {
    console.log(`Deleted object is hidden: ${error.message}`);
  }

  store.restore(backup);
  if (store.get("config/service.json").checksum !== firstVersion.checksum) {
    throw new IntegrityError("Restored object does not match the backup.");
  }

  pool.setHealth("vm-a", false);
  console.log("Policy after health change:", policy.evaluate(pool.report(), [backup]));

  const reportFile = path.join(os.tmpdir(), `architecture-${crypto.randomUUID()}.json`);
  try {
    await BackupService.writeReport(backup, reportFile);
    console.log("Backup report created:", reportFile);
  } finally {
    await fs.rm(reportFile, { force: true });
  }

  try {
    validateObjectKey("../secrets.txt");
  } catch (error) {
    console.log(`Unsafe key rejected: ${error.message}`);
  }

  const isolatedPool = new ComputePool([]);
  try {
    isolatedPool.acquire();
  } catch (error) {
    if (!(error instanceof CapacityError)) throw error;
    console.log("Empty compute pool correctly rejected the request.");
  }

  console.log("Architecture simulation completed successfully.");
}

main().catch((error) => {
  console.error("Fatal architecture error:", error.message);
  process.exitCode = 1;
});
