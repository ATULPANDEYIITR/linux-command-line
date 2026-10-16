"use strict";

/*
 * Object storage has two useful conceptual planes:
 * - The data plane moves object bytes.
 * - The control plane manages buckets, metadata, versions, lifecycle rules,
 *   and policies.
 *
 * This executable model focuses on the control-plane behavior while keeping
 * object content in memory so the example requires no npm dependencies.
 */

const crypto = require("node:crypto");

const StorageClass = Object.freeze({
  STANDARD: "STANDARD",
  INFREQUENT_ACCESS: "INFREQUENT_ACCESS",
  ARCHIVE: "ARCHIVE",
});

const VersioningState = Object.freeze({
  ENABLED: "ENABLED",
  SUSPENDED: "SUSPENDED",
});

class ObjectStorageError extends Error {}

class BucketAlreadyExistsError extends ObjectStorageError {}
class BucketNotFoundError extends ObjectStorageError {}
class ObjectNotFoundError extends ObjectStorageError {}
class InvalidOperationError extends ObjectStorageError {}

function sha256(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

class ObjectVersion {
  constructor({
    versionId,
    content,
    contentType,
    metadata,
    createdAt,
    storageClass = StorageClass.STANDARD,
    deleteMarker = false,
  }) {
    this.versionId = versionId;
    this.size = Buffer.byteLength(content);
    this.checksum = sha256(content);
    this.contentType = contentType;
    this.metadata = Object.freeze({ ...metadata });
    this.createdAt = new Date(createdAt);
    this.storageClass = storageClass;
    this.deleteMarker = deleteMarker;
  }
}

class StoredObject {
  constructor(key) {
    this.key = key;
    this.versions = [];
    this.metadata = {};
  }

  get currentVersion() {
    return this.versions.at(-1);
  }
}

class LifecycleRule {
  constructor({
    name,
    prefix,
    transitionAfterDays = null,
    transitionTo = null,
    expireAfterDays = null,
  }) {
    if (!name || !prefix) {
      throw new TypeError("Lifecycle rules require a name and prefix.");
    }

    if (
      transitionAfterDays !== null &&
      (!Number.isInteger(transitionAfterDays) || transitionAfterDays < 0)
    ) {
      throw new TypeError("Transition age must be a non-negative integer.");
    }

    if (transitionAfterDays !== null && transitionTo === null) {
      throw new TypeError("A transition age requires a target storage class.");
    }

    this.name = name;
    this.prefix = prefix;
    this.transitionAfterDays = transitionAfterDays;
    this.transitionTo = transitionTo;
    this.expireAfterDays = expireAfterDays;
  }
}

class Bucket {
  constructor(name, region) {
    if (!/^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$/.test(name)) {
      throw new TypeError("Invalid bucket name.");
    }

    this.name = name;
    this.region = region;
    this.versioning = VersioningState.ENABLED;
    this.objects = new Map();
    this.lifecycleRules = [];
  }

  addLifecycleRule(rule) {
    this.lifecycleRules.push(rule);
  }

  putObject({
    key,
    content,
    contentType = "application/octet-stream",
    metadata = {},
    createdAt = new Date(),
  }) {
    if (!key || key.startsWith("/")) {
      throw new TypeError("Object keys must be non-empty relative paths.");
    }

    const bytes = Buffer.isBuffer(content) ? content : Buffer.from(content);

    if (this.versioning === VersioningState.SUSPENDED) {
      const old = this.objects.get(key);
      if (old) old.versions.length = 0;
    }

    let object = this.objects.get(key);
    if (!object) {
      object = new StoredObject(key);
      this.objects.set(key, object);
    }

    object.metadata = { ...metadata };

    const versionId = sha256(
      `${this.name}:${key}:${sha256(bytes)}:${new Date(createdAt).toISOString()}`
    ).slice(0, 18);

    const version = new ObjectVersion({
      versionId,
      content: bytes,
      contentType,
      metadata,
      createdAt,
    });

    object.versions.push(version);
    return version;
  }

  getObject(key, versionId = null) {
    const object = this.objects.get(key);
    if (!object) throw new ObjectNotFoundError(key);

    const version = versionId
      ? object.versions.find((item) => item.versionId === versionId)
      : object.currentVersion;

    if (!version || version.deleteMarker) {
      throw new ObjectNotFoundError(`${key}@${versionId ?? "current"}`);
    }

    return version;
  }

  deleteObject(key, versionId = null, now = new Date()) {
    const object = this.objects.get(key);
    if (!object) throw new ObjectNotFoundError(key);

    if (versionId) {
      const index = object.versions.findIndex(
        (item) => item.versionId === versionId
      );
      if (index === -1) throw new ObjectNotFoundError(`${key}@${versionId}`);

      object.versions.splice(index, 1);
      if (object.versions.length === 0) this.objects.delete(key);
      return;
    }

    if (this.versioning === VersioningState.ENABLED) {
      const versionIdForMarker = sha256(
        `delete:${this.name}:${key}:${new Date(now).toISOString()}`
      ).slice(0, 18);

      object.versions.push(
        new ObjectVersion({
          versionId: versionIdForMarker,
          content: Buffer.alloc(0),
          contentType: "application/x-delete-marker",
          metadata: {},
          createdAt: now,
          deleteMarker: true,
        })
      );
    } else {
      this.objects.delete(key);
    }
  }

  listCurrentObjects(prefix = "") {
    return [...this.objects.values()]
      .filter((object) => object.key.startsWith(prefix))
      .map((object) => object.currentVersion)
      .filter((version) => version && !version.deleteMarker)
      .map((version) => ({
        key: this.objects.get(
          [...this.objects.values()].find((item) =>
            item.versions.includes(version)
          )?.key
        )?.key,
        versionId: version.versionId,
        size: version.size,
        storageClass: version.storageClass,
      }));
  }

  applyLifecycle(now) {
    const actions = [];

    for (const [key, object] of this.objects.entries()) {
      for (let index = object.versions.length - 1; index >= 0; index--) {
        const version = object.versions[index];
        if (version.deleteMarker) continue;

        const ageDays =
          (new Date(now).getTime() - version.createdAt.getTime()) /
          86_400_000;

        for (const rule of this.lifecycleRules) {
          if (!key.startsWith(rule.prefix)) continue;

          if (
            rule.transitionAfterDays !== null &&
            ageDays >= rule.transitionAfterDays &&
            version.storageClass !== rule.transitionTo
          ) {
            version.storageClass = rule.transitionTo;
            actions.push(
              `transition ${key}@${version.versionId} -> ${rule.transitionTo}`
            );
          }

          if (
            rule.expireAfterDays !== null &&
            ageDays >= rule.expireAfterDays
          ) {
            object.versions.splice(index, 1);
            actions.push(`expire ${key}@${version.versionId}`);
            break;
          }
        }
      }

      if (object.versions.length === 0) {
        this.objects.delete(key);
      }
    }

    return actions;
  }
}

class ObjectStorageService {
  constructor() {
    this.buckets = new Map();
  }

  createBucket(name, region) {
    if (this.buckets.has(name)) {
      throw new BucketAlreadyExistsError(name);
    }

    const bucket = new Bucket(name, region);
    this.buckets.set(name, bucket);
    return bucket;
  }

  getBucket(name) {
    const bucket = this.buckets.get(name);
    if (!bucket) throw new BucketNotFoundError(name);
    return bucket;
  }

  deleteBucket(name) {
    const bucket = this.getBucket(name);

    if (bucket.objects.size > 0) {
      throw new InvalidOperationError(
        "The bucket must be empty before deletion."
      );
    }

    this.buckets.delete(name);
  }
}

async function simulateEventDrivenLifecycle(bucket, now) {
  const lifecycleEvents = bucket.applyLifecycle(now);

  for (const event of lifecycleEvents) {
    await new Promise((resolve) => setImmediate(resolve));
    console.log(`[lifecycle-event] ${event}`);
  }
}

async function main() {
  const storage = new ObjectStorageService();
  const bucket = storage.createBucket("application-audit-store", "ap-south-1");

  const start = new Date("2026-01-01T00:00:00Z");

  bucket.addLifecycleRule(
    new LifecycleRule({
      name: "audit-to-archive",
      prefix: "audit/",
      transitionAfterDays: 30,
      transitionTo: StorageClass.INFREQUENT_ACCESS,
      expireAfterDays: 365,
    })
  );

  bucket.addLifecycleRule(
    new LifecycleRule({
      name: "reports-to-deep-archive",
      prefix: "reports/",
      transitionAfterDays: 90,
      transitionTo: StorageClass.ARCHIVE,
    })
  );

  const first = bucket.putObject({
    key: "reports/monthly.json",
    content: JSON.stringify({ month: "January", revenue: 84000 }),
    contentType: "application/json",
    metadata: {
      owner: "finance",
      classification: "internal",
    },
    createdAt: start,
  });

  bucket.putObject({
    key: "reports/monthly.json",
    content: JSON.stringify({ month: "January", revenue: 86500 }),
    contentType: "application/json",
    metadata: {
      owner: "finance",
      classification: "internal",
    },
    createdAt: new Date("2026-01-10T00:00:00Z"),
  });

  bucket.putObject({
    key: "audit/access.log",
    content: "principal=service-account action=GET object=reports/monthly.json",
    contentType: "text/plain",
    metadata: {
      retention: "regulated",
    },
    createdAt: start,
  });

  console.log("=== Object metadata ===");
  const current = bucket.getObject("reports/monthly.json");
  console.log({
    size: current.size,
    contentType: current.contentType,
    checksum: current.checksum,
    storageClass: current.storageClass,
    metadata: current.metadata,
  });

  console.log("\n=== Explicit version retrieval ===");
  console.log(bucket.getObject("reports/monthly.json", first.versionId));

  console.log("\n=== Lifecycle processing ===");
  await simulateEventDrivenLifecycle(
    bucket,
    new Date("2026-04-15T00:00:00Z")
  );

  console.log("\n=== Current versions ===");
  for (const [key, object] of bucket.objects) {
    console.log(
      key,
      object.currentVersion?.versionId,
      object.currentVersion?.storageClass
    );
  }

  console.log("\n=== Version-aware deletion ===");
  bucket.deleteObject("reports/monthly.json", first.versionId);
  console.log(
    bucket.objects.get("reports/monthly.json").versions.map(
      (version) => version.versionId
    )
  );

  console.log("\n=== Delete marker behavior ===");
  bucket.deleteObject("audit/access.log");

  try {
    bucket.getObject("audit/access.log");
  } catch (error) {
    if (error instanceof ObjectNotFoundError) {
      console.log("Current object is hidden by the delete marker.");
    } else {
      throw error;
    }
  }

  console.log("\n=== Control-plane failure ===");
  try {
    storage.deleteBucket(bucket.name);
  } catch (error) {
    console.log(error.message);
  }

  console.log("\n=== Integrity check ===");
  const surviving = bucket.getObject("reports/monthly.json");
  if (!/^[a-f0-9]{64}$/.test(surviving.checksum)) {
    throw new InvalidOperationError("Invalid checksum representation.");
  }
  console.log("Checksum format validated.");
}

main().catch((error) => {
  console.error("Fatal storage simulation error:", error);
  process.exitCode = 1;
});
