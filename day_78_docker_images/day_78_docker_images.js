"use strict";

/**
 * Docker Images: Event-driven image build and optimization engine.
 *
 * Runtime: Node.js 18+
 *
 * Features:
 * - Dockerfile instruction validation
 * - Content-addressed image layers
 * - Dependency-aware build cache
 * - Build events
 * - Asynchronous build execution
 * - Image manifests
 * - Multi-stage build modeling
 * - Image optimization policies
 * - Security analysis
 * - Build cancellation and failure handling
 */

const crypto = require("node:crypto");
const EventEmitter = require("node:events");

// ============================================================
// 1. Domain configuration
// ============================================================

const Instruction = Object.freeze({
    FROM: "FROM",
    WORKDIR: "WORKDIR",
    COPY: "COPY",
    ADD: "ADD",
    RUN: "RUN",
    ENV: "ENV",
    ARG: "ARG",
    USER: "USER",
    EXPOSE: "EXPOSE",
    LABEL: "LABEL",
    CMD: "CMD",
    ENTRYPOINT: "ENTRYPOINT"
});

const BaseImages = Object.freeze({
    "ubuntu:24.04": 29 * 1024 * 1024,
    "debian:bookworm-slim": 27 * 1024 * 1024,
    "python:3.13-slim": 45 * 1024 * 1024,
    "alpine:3.21": 8 * 1024 * 1024,
    "node:22-alpine": 18 * 1024 * 1024
});

class DockerBuildError extends Error {
    constructor(message, code = "BUILD_ERROR") {
        super(message);
        this.name = "DockerBuildError";
        this.code = code;
    }
}

function sha256(value) {
    return crypto
        .createHash("sha256")
        .update(value)
        .digest("hex");
}

// ============================================================
// 2. Dockerfile parsing
// ============================================================

class DockerfileParser {

    static parse(content) {
        if (typeof content !== "string" || !content.trim()) {
            throw new DockerBuildError(
                "Dockerfile must be a non-empty string.",
                "INVALID_DOCKERFILE"
            );
        }

        const instructions = [];

        content.split(/\r?\n/).forEach((original, index) => {
            const line = original.trim();

            if (!line || line.startsWith("#")) {
                return;
            }

            const match = line.match(/^([A-Za-z]+)\s+(.+)$/);

            if (!match) {
                throw new DockerBuildError(
                    `Invalid instruction on line ${index + 1}.`,
                    "PARSE_ERROR"
                );
            }

            const operation = match[1].toUpperCase();
            const argumentsText = match[2].trim();

            if (!Object.hasOwn(Instruction, operation)) {
                throw new DockerBuildError(
                    `Unsupported instruction: ${operation}`
                );
            }

            instructions.push(
                Object.freeze({
                    operation,
                    arguments: argumentsText,
                    line: index + 1
                })
            );
        });

        if (instructions.length === 0) {
            throw new DockerBuildError("No Dockerfile instructions found.");
        }

        if (instructions[0].operation !== "FROM") {
            throw new DockerBuildError(
                "The first instruction must be FROM."
            );
        }

        return instructions;
    }
}

// ============================================================
// 3. Build context
// ============================================================

class BuildContext {

    constructor(files, buildArgs = {}) {
        this.files = new Map();
        this.buildArgs = new Map(Object.entries(buildArgs));

        for (const [path, content] of Object.entries(files)) {
            this.addFile(path, content);
        }
    }

    addFile(path, content) {
        if (
            typeof path !== "string" ||
            path.startsWith("/") ||
            path.split("/").includes("..")
        ) {
            throw new DockerBuildError(
                `Unsafe build context path: ${path}`,
                "UNSAFE_PATH"
            );
        }

        if (!Buffer.isBuffer(content)) {
            throw new DockerBuildError(
                `File content must be a Buffer: ${path}`
            );
        }

        this.files.set(path, Buffer.from(content));
    }

    fingerprint() {
        const hash = crypto.createHash("sha256");

        const entries = [...this.files.entries()]
            .sort(([a], [b]) => a.localeCompare(b));

        for (const [path, content] of entries) {
            hash.update(path);
            hash.update("\0");
            hash.update(content);
            hash.update("\0");
        }

        return hash.digest("hex");
    }

    hasFile(path) {
        return this.files.has(path);
    }

    getFileSize(path) {
        const file = this.files.get(path);

        if (!file) {
            throw new DockerBuildError(
                `File not found: ${path}`,
                "MISSING_FILE"
            );
        }

        return file.length;
    }
}

// ============================================================
// 4. Layer cache
// ============================================================

class LayerCache {

    constructor() {
        this.layers = new Map();
        this.hits = 0;
        this.misses = 0;
    }

    get(key) {
        const layer = this.layers.get(key);

        if (layer) {
            this.hits++;
            return layer;
        }

        this.misses++;
        return undefined;
    }

    set(key, layer) {
        this.layers.set(key, Object.freeze({ ...layer }));
    }

    getStatistics() {
        const total = this.hits + this.misses;

        return {
            entries: this.layers.size,
            hits: this.hits,
            misses: this.misses,
            hitRate: total === 0 ? 0 : this.hits / total
        };
    }
}

// ============================================================
// 5. Build event system
// ============================================================

class BuildMonitor extends EventEmitter {

    constructor() {
        super();
        this.events = [];
    }

    record(type, details = {}) {
        const event = Object.freeze({
            type,
            timestamp: new Date().toISOString(),
            ...details
        });

        this.events.push(event);
        this.emit(type, event);
    }

    getHistory() {
        return [...this.events];
    }
}

// ============================================================
// 6. Image model
// ============================================================

class DockerImage {

    constructor(name, tag, architecture = "linux/amd64") {
        this.name = name;
        this.tag = tag;
        this.architecture = architecture;
        this.layers = [];
        this.metadata = {};
    }

    addLayer(layer) {
        this.layers.push(Object.freeze({ ...layer }));
    }

    get sizeBytes() {
        return this.layers.reduce(
            (total, layer) => total + layer.sizeBytes,
            0
        );
    }

    get sizeMB() {
        return this.sizeBytes / (1024 * 1024);
    }

    get id() {
        return sha256(
            this.layers.map(layer => layer.digest).join("")
        );
    }

    manifest() {
        return {
            name: this.name,
            tag: this.tag,
            id: this.id,
            architecture: this.architecture,
            layerCount: this.layers.length,
            sizeBytes: this.sizeBytes,
            layers: this.layers.map(layer => ({
                digest: layer.digest,
                instruction: layer.instruction,
                sizeBytes: layer.sizeBytes
            }))
        };
    }
}

// ============================================================
// 7. Policy evaluation
// ============================================================

class ImagePolicy {

    constructor(options = {}) {
        this.maxLayers = options.maxLayers ?? 20;
        this.maxSizeMB = options.maxSizeMB ?? 500;
        this.requireNonRoot = options.requireNonRoot ?? true;
        this.rejectLatest = options.rejectLatest ?? true;
    }

    evaluate(image, instructions) {
        const findings = [];

        if (image.layers.length > this.maxLayers) {
            findings.push({
                severity: "HIGH",
                rule: "MAX_LAYERS",
                message: "Image exceeds the layer-count limit."
            });
        }

        if (image.sizeMB > this.maxSizeMB) {
            findings.push({
                severity: "HIGH",
                rule: "MAX_IMAGE_SIZE",
                message: "Image exceeds the permitted size."
            });
        }

        if (
            this.requireNonRoot &&
            !instructions.some(item =>
                item.operation === "USER" &&
                item.arguments.toLowerCase() !== "root" &&
                item.arguments !== "0"
            )
        ) {
            findings.push({
                severity: "HIGH",
                rule: "NON_ROOT_USER",
                message: "The image does not explicitly select a non-root user."
            });
        }

        if (
            this.rejectLatest &&
            instructions.some(item =>
                item.operation === "FROM" &&
                item.arguments.split(/\s+/)[0].endsWith(":latest")
            )
        ) {
            findings.push({
                severity: "MEDIUM",
                rule: "MUTABLE_TAG",
                message: "A mutable latest base-image tag is used."
            });
        }

        return findings;
    }
}

// ============================================================
// 8. Docker image builder
// ============================================================

class DockerBuilder {

    constructor({
        cache = new LayerCache(),
        monitor = new BuildMonitor(),
        policy = new ImagePolicy()
    } = {}) {
        this.cache = cache;
        this.monitor = monitor;
        this.policy = policy;
    }

    async build({
        dockerfile,
        context,
        imageName,
        tag = "latest",
        signal
    }) {
        const started = performance.now();

        if (!(context instanceof BuildContext)) {
            throw new DockerBuildError("Invalid build context.");
        }

        if (!/^[a-z0-9][a-z0-9._/-]*$/.test(imageName)) {
            throw new DockerBuildError("Invalid image name.");
        }

        if (!/^[A-Za-z0-9_.-]+$/.test(tag)) {
            throw new DockerBuildError("Invalid image tag.");
        }

        const instructions = DockerfileParser.parse(dockerfile);
        const contextHash = context.fingerprint();

        const image = new DockerImage(imageName, tag);

        let parentDigest = null;
        let currentUser = "root";
        let cachedLayers = 0;
        let createdLayers = 0;

        this.monitor.record("build-started", {
            image: `${imageName}:${tag}`
        });

        try {
            for (const item of instructions) {

                if (signal?.aborted) {
                    throw new DockerBuildError(
                        "Build was cancelled.",
                        "BUILD_CANCELLED"
                    );
                }

                await new Promise(resolve => setImmediate(resolve));

                const { operation, arguments: args } = item;

                let sizeBytes = 0;

                switch (operation) {

                    case "FROM": {
                        const base = args.split(/\s+/)[0];

                        if (!Object.hasOwn(BaseImages, base)) {
                            throw new DockerBuildError(
                                `Unsupported base image: ${base}`
                            );
                        }

                        sizeBytes = BaseImages[base];
                        break;
                    }

                    case "COPY":
                    case "ADD": {
                        const parts = args.split(/\s+/);

                        if (parts.length < 2) {
                            throw new DockerBuildError(
                                `${operation} requires source and destination.`
                            );
                        }

                        if (!context.hasFile(parts[0])) {
                            throw new DockerBuildError(
                                `Missing file: ${parts[0]}`
                            );
                        }

                        sizeBytes = context.getFileSize(parts[0]);
                        break;
                    }

                    case "RUN": {
                        if (!args.trim()) {
                            throw new DockerBuildError("Empty RUN instruction.");
                        }

                        sizeBytes = this.estimateCommandSize(args);
                        break;
                    }

                    case "USER":
                        currentUser = args;
                        break;

                    case "ENV":
                        if (!/^[A-Za-z_][A-Za-z0-9_]*=/.test(args)) {
                            throw new DockerBuildError("Invalid ENV syntax.");
                        }
                        break;

                    case "ARG":
                        if (!/^[A-Za-z_][A-Za-z0-9_]*(?:=.*)?$/.test(args)) {
                            throw new DockerBuildError("Invalid ARG syntax.");
                        }
                        break;

                    case "EXPOSE": {
                        const port = Number(args.split("/")[0]);

                        if (!Number.isInteger(port) || port < 1 || port > 65535) {
                            throw new DockerBuildError("Invalid exposed port.");
                        }
                        break;
                    }

                    case "WORKDIR":
                        if (args.split("/").includes("..")) {
                            throw new DockerBuildError("Unsafe WORKDIR.");
                        }
                        break;

                    default:
                        break;
                }

                const cacheKey = sha256(JSON.stringify({
                    instruction: operation,
                    arguments: args,
                    parentDigest,
                    contextHash,
                    buildArgs: [...context.buildArgs.entries()].sort(),
                    currentUser
                }));

                let layer = this.cache.get(cacheKey);

                if (layer) {
                    cachedLayers++;
                    this.monitor.record("layer-cached", {
                        instruction: operation,
                        digest: layer.digest
                    });
                } else {
                    const digest = sha256(
                        `${cacheKey}:${sizeBytes}`
                    );

                    layer = {
                        digest,
                        instruction: `${operation} ${args}`,
                        sizeBytes,
                        parentDigest
                    };

                    this.cache.set(cacheKey, layer);
                    createdLayers++;

                    this.monitor.record("layer-created", {
                        instruction: operation,
                        digest
                    });
                }

                image.addLayer(layer);
                parentDigest = layer.digest;
            }

            const findings = this.policy.evaluate(
                image,
                instructions
            );

            image.metadata = {
                createdAt: new Date().toISOString(),
                findings
            };

            this.monitor.record("build-completed", {
                imageId: image.id,
                findings: findings.length
            });

            return {
                status: "SUCCESS",
                image,
                cachedLayers,
                createdLayers,
                findings,
                durationMs: performance.now() - started
            };

        } catch (error) {
            this.monitor.record("build-failed", {
                error: error.message,
                code: error.code ?? "UNKNOWN"
            });

            throw error;
        }
    }

    estimateCommandSize(command) {
        const value = command.toLowerCase();

        if (value.includes("apt-get install")) {
            return 25 * 1024 * 1024;
        }

        if (value.includes("pip install")) {
            return 15 * 1024 * 1024;
        }

        if (value.includes("npm install")) {
            return 20 * 1024 * 1024;
        }

        if (value.includes("apk add")) {
            return 8 * 1024 * 1024;
        }

        return 1024 * 1024;
    }
}

// ============================================================
// 9. Multi-stage image model
// ============================================================

class MultiStageBuild {

    constructor() {
        this.stages = new Map();
    }

    addStage(name, baseImage, artifacts = []) {
        if (this.stages.has(name)) {
            throw new DockerBuildError(
                `Duplicate stage: ${name}`
            );
        }

        if (!Object.hasOwn(BaseImages, baseImage)) {
            throw new DockerBuildError(
                `Unknown stage base image: ${baseImage}`
            );
        }

        this.stages.set(name, {
            name,
            baseImage,
            artifacts: [...artifacts]
        });
    }

    estimateRuntimeSize(name) {
        const stage = this.stages.get(name);

        if (!stage) {
            throw new DockerBuildError("Stage not found.");
        }

        const sizes = {
            application: 5 * 1024 * 1024,
            binary: 12 * 1024 * 1024,
            assets: 2 * 1024 * 1024
        };

        return BaseImages[stage.baseImage] +
            stage.artifacts.reduce(
                (total, artifact) => total + (sizes[artifact] ?? 0),
                0
            );
    }
}

// ============================================================
// 10. Demonstration
// ============================================================

async function main() {

    const dockerfile = `
FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app.py .
ENV APP_ENV=production
EXPOSE 8000
USER 10001
CMD python app.py
`;

    const context = new BuildContext({
        "requirements.txt": Buffer.from("fastapi==0.115.6\n"),
        "app.py": Buffer.from("print('Application started')\n")
    });

    const monitor = new BuildMonitor();

    monitor.on("layer-created", event => {
        console.log(`[NEW LAYER] ${event.instruction}`);
    });

    monitor.on("layer-cached", event => {
        console.log(`[CACHE HIT] ${event.instruction}`);
    });

    const builder = new DockerBuilder({
        monitor,
        policy: new ImagePolicy({
            maxLayers: 15,
            maxSizeMB: 150,
            requireNonRoot: true
        })
    });

    console.log("\nFIRST BUILD");

    const first = await builder.build({
        dockerfile,
        context,
        imageName: "learning-api",
        tag: "1.0"
    });

    console.log("\nIMAGE MANIFEST");

    console.log(JSON.stringify(first.image.manifest(), null, 2));

    console.log("\nSECOND BUILD");

    const second = await builder.build({
        dockerfile,
        context,
        imageName: "learning-api",
        tag: "1.0"
    });

    console.log({
        cachedLayers: second.cachedLayers,
        createdLayers: second.createdLayers,
        sizeMB: second.image.sizeMB.toFixed(2)
    });

    console.log("\nPOLICY FINDINGS");

    console.log(first.findings);

    console.log("\nMULTI-STAGE BUILD");

    const stages = new MultiStageBuild();

    stages.addStage(
        "builder",
        "python:3.13-slim",
        ["application"]
    );

    stages.addStage(
        "runtime",
        "alpine:3.21",
        ["application", "assets"]
    );

    console.log(
        "Runtime size:",
        (
            stages.estimateRuntimeSize("runtime") /
            (1024 * 1024)
        ).toFixed(2),
        "MB"
    );

    console.log("\nCACHE STATISTICS");
    console.log(builder.cache.getStatistics());

    console.log("\nBUILD EVENT COUNT:", monitor.getHistory().length);

    console.assert(first.status === "SUCCESS");
    console.assert(second.cachedLayers === second.image.layers.length);
    console.assert(first.image.id === second.image.id);

    console.log("\nAll demonstrations completed.");
}

main().catch(error => {
    console.error("BUILD ERROR:", error.message);
    process.exitCode = 1;
});
