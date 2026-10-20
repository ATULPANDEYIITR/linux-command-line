"use strict";

const fs = require("node:fs/promises");
const path = require("node:path");
const crypto = require("node:crypto");
const os = require("node:os");

class BackupError extends Error {}

async function sha256File(filePath) {
    const hash = crypto.createHash("sha256");
    const data = await fs.readFile(filePath);
    hash.update(data);
    return hash.digest("hex");
}

async function scanDirectory(root) {
    const result = new Map();

    async function walk(current) {
        const entries = await fs.readdir(current, { withFileTypes: true });

        for (const entry of entries) {
            const fullPath = path.join(current, entry.name);

            if (entry.isDirectory()) {
                await walk(fullPath);
                continue;
            }

            if (!entry.isFile()) {
                continue;
            }

            const relativePath = path.relative(root, fullPath).split(path.sep).join("/");
            const stat = await fs.stat(fullPath);

            result.set(relativePath, {
                relativePath,
                size: stat.size,
                modifiedMs: stat.mtimeMs,
                sha256: await sha256File(fullPath),
            });
        }
    }

    await walk(root);
    return result;
}

class BackupRepository {
    constructor(repositoryPath) {
        this.repositoryPath = repositoryPath;
    }

    async initialize() {
        await fs.mkdir(this.repositoryPath, { recursive: true });
    }

    backupPath(id) {
        return path.join(this.repositoryPath, id);
    }

    async writeManifest(directory, manifest) {
        await fs.writeFile(
            path.join(directory, "manifest.json"),
            JSON.stringify(manifest, null, 2),
            "utf8"
        );
    }

    async createBackup(source, type = "full", parent = null, timestamp = new Date()) {
        const files = await scanDirectory(source);

        if (type === "incremental" && !parent) {
            throw new BackupError("An incremental backup requires a parent backup");
        }

        const selected =
            type === "full"
                ? files
                : new Map(
                    [...files].filter(([name, fingerprint]) => {
                        const old = parent.files[name];
                        return !old ||
                            old.size !== fingerprint.size ||
                            old.modifiedMs !== fingerprint.modifiedMs ||
                            old.sha256 !== fingerprint.sha256;
                    })
                );

        const prefix = type === "full" ? "full" : "inc";
        const id = `${prefix}-${timestamp.toISOString().replace(/[-:.TZ]/g, "")}`;
        const finalDirectory = this.backupPath(id);
        const temporaryDirectory = await fs.mkdtemp(
            path.join(this.repositoryPath, `.${id}-`)
        );

        try {
            const dataDirectory = path.join(temporaryDirectory, "data");
            await fs.mkdir(dataDirectory, { recursive: true });

            for (const [relativePath] of selected) {
                // Resolve and verify the target before writing. Backup metadata
                // must never be allowed to escape the backup data directory.
                const target = path.resolve(dataDirectory, relativePath);
                if (!target.startsWith(path.resolve(dataDirectory) + path.sep)) {
                    throw new BackupError(`Unsafe path: ${relativePath}`);
                }

                const sourceFile = path.join(source, relativePath);
                await fs.mkdir(path.dirname(target), { recursive: true });
                await fs.copyFile(sourceFile, target);
            }

            const manifest = {
                id,
                type,
                createdAt: timestamp.toISOString(),
                source: path.resolve(source),
                parentId: parent ? parent.id : null,
                files: Object.fromEntries(selected),
            };

            await this.writeManifest(temporaryDirectory, manifest);
            await fs.rename(temporaryDirectory, finalDirectory);
            return manifest;
        } catch (error) {
            await fs.rm(temporaryDirectory, { recursive: true, force: true });
            throw error;
        }
    }

    async verify(manifest) {
        const errors = [];
        const dataDirectory = path.join(this.backupPath(manifest.id), "data");

        for (const [relativePath, expected] of Object.entries(manifest.files)) {
            const target = path.resolve(dataDirectory, relativePath);

            if (!target.startsWith(path.resolve(dataDirectory) + path.sep)) {
                errors.push(`Unsafe path: ${relativePath}`);
                continue;
            }

            try {
                const stat = await fs.stat(target);

                if (!stat.isFile()) {
                    errors.push(`Not a regular file: ${relativePath}`);
                    continue;
                }

                if (stat.size !== expected.size) {
                    errors.push(`Size mismatch: ${relativePath}`);
                    continue;
                }

                const actualHash = await sha256File(target);
                if (actualHash !== expected.sha256) {
                    errors.push(`Checksum mismatch: ${relativePath}`);
                }
            } catch {
                errors.push(`Missing file: ${relativePath}`);
            }
        }

        return {
            valid: errors.length === 0,
            errors,
        };
    }

    async restoreChain(manifests, targetDirectory) {
        if (!Array.isArray(manifests) || manifests.length === 0) {
            throw new BackupError("A non-empty backup chain is required");
        }

        const ordered = [...manifests].sort(
            (a, b) => new Date(a.createdAt) - new Date(b.createdAt)
        );

        if (ordered[0].type !== "full") {
            throw new BackupError("A restore chain must begin with a full backup");
        }

        await fs.mkdir(targetDirectory, { recursive: true });

        for (const manifest of ordered) {
            const verification = await this.verify(manifest);
            if (!verification.valid) {
                throw new BackupError(
                    `Cannot restore ${manifest.id}: ${verification.errors.join(", ")}`
                );
            }

            for (const relativePath of Object.keys(manifest.files)) {
                const sourceFile = path.join(
                    this.backupPath(manifest.id),
                    "data",
                    relativePath
                );
                const targetFile = path.resolve(targetDirectory, relativePath);

                if (!targetFile.startsWith(path.resolve(targetDirectory) + path.sep)) {
                    throw new BackupError(`Unsafe restore path: ${relativePath}`);
                }

                await fs.mkdir(path.dirname(targetFile), { recursive: true });
                await fs.copyFile(sourceFile, targetFile);
            }
        }
    }
}

class RetentionPolicy {
    constructor({ dailyDays = 7, weeklyWeeks = 4 }) {
        if (dailyDays < 1 || weeklyWeeks < 1) {
            throw new RangeError("Retention values must be positive");
        }

        this.dailyDays = dailyDays;
        this.weeklyWeeks = weeklyWeeks;
    }

    shouldKeep(manifest, now = new Date()) {
        const ageMs = now - new Date(manifest.createdAt);
        const day = 24 * 60 * 60 * 1000;

        if (ageMs <= this.dailyDays * day) {
            return true;
        }

        // Older backups are retained when they are the first backup observed
        // in a calendar week. This keeps a practical weekly recovery point.
        const date = new Date(manifest.createdAt);
        const ageWeeks = ageMs / (7 * day);

        return ageWeeks <= this.weeklyWeeks && date.getUTCDay() === 0;
    }
}

async function main() {
    const workspace = await fs.mkdtemp(path.join(os.tmpdir(), "backup-demo-"));
    const source = path.join(workspace, "source");
    const repositoryPath = path.join(workspace, "repository");
    const restored = path.join(workspace, "restored");

    await fs.mkdir(path.join(source, "config"), { recursive: true });
    await fs.mkdir(path.join(source, "logs"), { recursive: true });

    await fs.writeFile(
        path.join(source, "config", "service.json"),
        JSON.stringify({ environment: "production", version: 1 }, null, 2)
    );
    await fs.writeFile(
        path.join(source, "logs", "service.log"),
        "started\n"
    );

    const repository = new BackupRepository(repositoryPath);
    await repository.initialize();

    const full = await repository.createBackup(
        source,
        "full",
        null,
        new Date("2026-10-01T02:00:00Z")
    );

    await fs.appendFile(
        path.join(source, "logs", "service.log"),
        "request processed\n"
    );
    await fs.writeFile(
        path.join(source, "config", "feature.json"),
        JSON.stringify({ snapshots: true })
    );

    const incremental = await repository.createBackup(
        source,
        "incremental",
        full,
        new Date("2026-10-02T02:00:00Z")
    );

    console.log("Full verification:", await repository.verify(full));
    console.log("Incremental verification:", await repository.verify(incremental));

    await repository.restoreChain([full, incremental], restored);

    const restoredLog = await fs.readFile(
        path.join(restored, "logs", "service.log"),
        "utf8"
    );

    console.log("Restored log:");
    console.log(restoredLog);

    const policy = new RetentionPolicy({
        dailyDays: 7,
        weeklyWeeks: 4,
    });

    console.log(
        "Keep full backup:",
        policy.shouldKeep(full, new Date("2026-10-03T00:00:00Z"))
    );
}

main().catch((error) => {
    console.error(`Backup operation failed: ${error.message}`);
    process.exitCode = 1;
});
