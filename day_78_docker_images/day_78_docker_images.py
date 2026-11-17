#!/usr/bin/env python3
"""
Docker Images: Layers, Dockerfiles, Image Optimization, and Build Processes.

A self-contained Docker image build simulator demonstrating:
- Dockerfile instruction processing
- Image layers and immutable layer metadata
- Content-based layer caching
- Build dependency tracking
- Multi-stage builds
- Image size estimation
- Layer reuse
- Image optimization
- Build validation and failure handling
- Reproducible build configuration
- Security and efficiency checks

Run:
    python docker_images.py
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ============================================================
# 1. Domain types
# ============================================================

class InstructionType(Enum):
    FROM = "FROM"
    WORKDIR = "WORKDIR"
    COPY = "COPY"
    ADD = "ADD"
    RUN = "RUN"
    ENV = "ENV"
    ARG = "ARG"
    EXPOSE = "EXPOSE"
    USER = "USER"
    LABEL = "LABEL"
    CMD = "CMD"
    ENTRYPOINT = "ENTRYPOINT"


class BuildStatus(Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CACHED = "CACHED"


@dataclass(frozen=True)
class DockerInstruction:
    instruction: InstructionType
    arguments: str


@dataclass(frozen=True)
class ImageLayer:
    digest: str
    instruction: str
    size_bytes: int
    created_at: float
    parent_digest: Optional[str] = None

    @property
    def size_mb(self) -> float:
        return self.size_bytes / (1024 * 1024)


@dataclass
class DockerImage:
    name: str
    tag: str
    layers: list[ImageLayer] = field(default_factory=list)
    architecture: str = "linux/amd64"

    @property
    def total_size(self) -> int:
        return sum(layer.size_bytes for layer in self.layers)

    @property
    def total_size_mb(self) -> float:
        return self.total_size / (1024 * 1024)

    @property
    def image_id(self) -> str:
        content = "".join(layer.digest for layer in self.layers)
        return hashlib.sha256(content.encode()).hexdigest()

    @property
    def layer_count(self) -> int:
        return len(self.layers)


@dataclass
class BuildResult:
    status: BuildStatus
    image: Optional[DockerImage]
    cached_layers: int
    created_layers: int
    errors: list[str]
    duration_seconds: float


# ============================================================
# 2. Dockerfile parser
# ============================================================

class DockerfileParser:
    VALID_INSTRUCTIONS = {
        item.value: item for item in InstructionType
    }

    @classmethod
    def parse(cls, content: str) -> list[DockerInstruction]:
        if not content.strip():
            raise ValueError("Dockerfile cannot be empty.")

        instructions = []

        for line_number, original in enumerate(content.splitlines(), 1):
            line = original.strip()

            if not line or line.startswith("#"):
                continue

            parts = line.split(maxsplit=1)

            if len(parts) != 2:
                raise ValueError(
                    f"Invalid instruction at line {line_number}."
                )

            keyword, arguments = parts
            keyword = keyword.upper()

            if keyword not in cls.VALID_INSTRUCTIONS:
                raise ValueError(
                    f"Unsupported instruction '{keyword}' "
                    f"at line {line_number}."
                )

            if not arguments.strip():
                raise ValueError(
                    f"Missing arguments at line {line_number}."
                )

            instructions.append(
                DockerInstruction(
                    cls.VALID_INSTRUCTIONS[keyword],
                    arguments.strip()
                )
            )

        if not instructions:
            raise ValueError("No valid Dockerfile instructions found.")

        if instructions[0].instruction != InstructionType.FROM:
            raise ValueError("Dockerfile must begin with FROM.")

        return instructions


# ============================================================
# 3. Layer cache
# ============================================================

class LayerCache:
    """
    Stores immutable build layers by content-derived cache keys.

    The same instruction can produce a different layer when its
    parent layer or build inputs change.
    """

    def __init__(self):
        self._layers: dict[str, ImageLayer] = {}

    @staticmethod
    def make_key(
        instruction: str,
        parent_digest: Optional[str],
        build_context_hash: str,
        arguments: dict[str, str]
    ) -> str:
        payload = {
            "instruction": instruction,
            "parent": parent_digest,
            "context": build_context_hash,
            "arguments": sorted(arguments.items())
        }

        serialized = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":")
        )

        return hashlib.sha256(
            serialized.encode()
        ).hexdigest()

    def get(self, key: str) -> Optional[ImageLayer]:
        return self._layers.get(key)

    def store(self, key: str, layer: ImageLayer) -> None:
        self._layers[key] = layer

    def clear(self) -> None:
        self._layers.clear()

    @property
    def count(self) -> int:
        return len(self._layers)


# ============================================================
# 4. Build context
# ============================================================

@dataclass
class BuildContext:
    files: dict[str, bytes]
    build_args: dict[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        for path, content in self.files.items():
            if path.startswith("/"):
                raise ValueError(
                    f"Build context paths must be relative: {path}"
                )

            if ".." in path.split("/"):
                raise ValueError(
                    f"Path traversal detected: {path}"
                )

            if not isinstance(content, bytes):
                raise TypeError(
                    f"File content must be bytes: {path}"
                )

    def fingerprint(self) -> str:
        digest = hashlib.sha256()

        for path in sorted(self.files):
            digest.update(path.encode())
            digest.update(b"\0")
            digest.update(self.files[path])
            digest.update(b"\0")

        return digest.hexdigest()


# ============================================================
# 5. Docker image builder
# ============================================================

class DockerBuildError(Exception):
    pass


class DockerImageBuilder:

    BASE_IMAGES = {
        "ubuntu:24.04": 29 * 1024 * 1024,
        "debian:bookworm-slim": 27 * 1024 * 1024,
        "python:3.13-slim": 45 * 1024 * 1024,
        "alpine:3.21": 8 * 1024 * 1024,
        "node:22-alpine": 18 * 1024 * 1024,
    }

    def __init__(self, cache: Optional[LayerCache] = None):
        self.cache = cache or LayerCache()

    def build(
        self,
        dockerfile: str,
        context: BuildContext,
        image_name: str,
        tag: str = "latest"
    ) -> BuildResult:

        started = time.perf_counter()
        errors = []
        cached_count = 0
        created_count = 0

        try:
            context.validate()
            instructions = DockerfileParser.parse(dockerfile)

            image = DockerImage(image_name, tag)
            context_hash = context.fingerprint()
            arguments = dict(context.build_args)

            previous_digest = None
            current_user = "root"
            working_directory = "/"

            for index, item in enumerate(instructions):

                operation = item.instruction
                value = item.arguments

                if operation == InstructionType.FROM:
                    if index != 0:
                        raise DockerBuildError(
                            "Additional FROM instructions require "
                            "a separately modeled build stage."
                        )

                    base_name = value.split()[0]

                    if base_name not in self.BASE_IMAGES:
                        raise DockerBuildError(
                            f"Unknown base image: {base_name}"
                        )

                    size = self.BASE_IMAGES[base_name]

                elif operation == InstructionType.WORKDIR:
                    if ".." in value.split("/"):
                        raise DockerBuildError(
                            "Unsafe WORKDIR path."
                        )

                    working_directory = value

                    size = 0

                elif operation in (
                    InstructionType.COPY,
                    InstructionType.ADD
                ):
                    parts = value.split()

                    if len(parts) < 2:
                        raise DockerBuildError(
                            "COPY and ADD require source and destination."
                        )

                    source = parts[0]

                    if source not in context.files:
                        raise DockerBuildError(
                            f"Missing build-context file: {source}"
                        )

                    size = len(context.files[source])

                elif operation == InstructionType.RUN:
                    if not value:
                        raise DockerBuildError("Empty RUN instruction.")

                    size = self._estimate_run_size(value)

                elif operation == InstructionType.ENV:
                    if "=" not in value:
                        raise DockerBuildError(
                            "ENV must use KEY=VALUE syntax."
                        )

                    size = 0

                elif operation == InstructionType.ARG:
                    key = value.split("=", 1)[0]

                    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
                        raise DockerBuildError("Invalid ARG name.")

                    size = 0

                elif operation == InstructionType.USER:
                    current_user = value
                    size = 0

                elif operation == InstructionType.EXPOSE:
                    if not re.fullmatch(r"\d{1,5}(?:/(tcp|udp))?", value):
                        raise DockerBuildError(
                            f"Invalid exposed port: {value}"
                        )

                    port = int(value.split("/")[0])

                    if not 1 <= port <= 65535:
                        raise DockerBuildError("Port outside valid range.")

                    size = 0

                else:
                    # Metadata instructions do not add filesystem data.
                    size = 0

                instruction_text = (
                    f"{operation.value} {value}"
                )

                if operation == InstructionType.FROM:
                    instruction_text += f" [{value}]"

                key = self.cache.make_key(
                    instruction_text,
                    previous_digest,
                    context_hash,
                    arguments
                )

                cached_layer = self.cache.get(key)

                if cached_layer is not None:
                    layer = cached_layer
                    cached_count += 1
                else:
                    digest = hashlib.sha256(
                        (
                            key
                            + str(size)
                            + working_directory
                            + current_user
                        ).encode()
                    ).hexdigest()

                    layer = ImageLayer(
                        digest=digest,
                        instruction=instruction_text,
                        size_bytes=size,
                        created_at=time.time(),
                        parent_digest=previous_digest
                    )

                    self.cache.store(key, layer)
                    created_count += 1

                image.layers.append(layer)
                previous_digest = layer.digest

            return BuildResult(
                BuildStatus.SUCCESS,
                image,
                cached_count,
                created_count,
                errors,
                time.perf_counter() - started
            )

        except (ValueError, TypeError, DockerBuildError) as exc:
            errors.append(str(exc))

            return BuildResult(
                BuildStatus.FAILED,
                None,
                cached_count,
                created_count,
                errors,
                time.perf_counter() - started
            )

    @staticmethod
    def _estimate_run_size(command: str) -> int:
        """
        Demonstration estimates, not measurements of actual
        operating-system package installation.
        """

        lowered = command.lower()

        if "apt-get install" in lowered:
            return 25 * 1024 * 1024

        if "pip install" in lowered:
            return 15 * 1024 * 1024

        if "npm install" in lowered:
            return 20 * 1024 * 1024

        if "apk add" in lowered:
            return 8 * 1024 * 1024

        return 1024 * 1024


# ============================================================
# 6. Image optimization analyzer
# ============================================================

@dataclass
class OptimizationFinding:
    severity: str
    message: str
    recommendation: str


class ImageOptimizer:

    @staticmethod
    def analyze(dockerfile: str) -> list[OptimizationFinding]:
        findings = []
        lines = dockerfile.splitlines()

        run_commands = [
            line.strip()
            for line in lines
            if line.strip().upper().startswith("RUN ")
        ]

        copy_lines = [
            line.strip()
            for line in lines
            if line.strip().upper().startswith("COPY ")
        ]

        if any("apt-get install" in line.lower()
               for line in run_commands):

            if not any(
                "apt-get clean" in line.lower()
                for line in run_commands
            ):
                findings.append(
                    OptimizationFinding(
                        "MEDIUM",
                        "Package manager cleanup is not detected.",
                        "Remove package lists and temporary files "
                        "within the same RUN instruction."
                    )
                )

        if len(run_commands) > 3:
            findings.append(
                OptimizationFinding(
                    "LOW",
                    "Multiple RUN instructions were detected.",
                    "Combine related shell operations when doing so "
                    "preserves cache behavior and readability."
                )
            )

        if not any(
            line.upper().startswith("USER ")
            for line in lines
        ):
            findings.append(
                OptimizationFinding(
                    "HIGH",
                    "No explicit non-root USER instruction.",
                    "Run the application as a dedicated non-root user."
                )
            )

        if any(
            line.upper().startswith("FROM ") and ":latest" in line
            for line in lines
        ):
            findings.append(
                OptimizationFinding(
                    "MEDIUM",
                    "A mutable latest image tag was detected.",
                    "Use a controlled image version or verified digest."
                )
            )

        if any(
            "COPY . ." in line
            for line in copy_lines
        ):
            findings.append(
                OptimizationFinding(
                    "MEDIUM",
                    "The complete build context is copied.",
                    "Use targeted COPY instructions and a .dockerignore "
                    "file to exclude unnecessary files."
                )
            )

        return findings


# ============================================================
# 7. Multi-stage build model
# ============================================================

@dataclass
class BuildStage:
    name: str
    base_image: str
    installed_components: list[str] = field(default_factory=list)
    copied_artifacts: list[str] = field(default_factory=list)


class MultiStageBuild:

    def __init__(self):
        self.stages: list[BuildStage] = []

    def add_stage(self, stage: BuildStage) -> None:
        if any(existing.name == stage.name for existing in self.stages):
            raise ValueError("Stage names must be unique.")

        self.stages.append(stage)

    def estimate_final_size(self, final_stage: str) -> int:
        stage = next(
            (
                item for item in self.stages
                if item.name == final_stage
            ),
            None
        )

        if stage is None:
            raise ValueError("Final stage does not exist.")

        base_size = DockerImageBuilder.BASE_IMAGES.get(
            stage.base_image
        )

        if base_size is None:
            raise ValueError("Unknown final-stage base image.")

        artifact_sizes = {
            "application": 5 * 1024 * 1024,
            "binary": 12 * 1024 * 1024,
            "static-assets": 2 * 1024 * 1024,
        }

        return base_size + sum(
            artifact_sizes.get(name, 0)
            for name in stage.copied_artifacts
        )


# ============================================================
# 8. Build report
# ============================================================

def display_image_report(result: BuildResult) -> None:

    if result.status == BuildStatus.FAILED:
        print("\nBUILD FAILED")

        for error in result.errors:
            print(f"  ERROR: {error}")

        return

    image = result.image

    print("\nIMAGE BUILD REPORT")
    print("=" * 65)
    print(f"Image:           {image.name}:{image.tag}")
    print(f"Image ID:        {image.image_id[:20]}")
    print(f"Architecture:    {image.architecture}")
    print(f"Layer count:     {image.layer_count}")
    print(f"Total size:      {image.total_size_mb:.2f} MB")
    print(f"Cached layers:   {result.cached_layers}")
    print(f"New layers:      {result.created_layers}")
    print(f"Build duration:  {result.duration_seconds:.6f} seconds")

    print("\nLAYER DETAILS")

    for index, layer in enumerate(image.layers, 1):
        print(
            f"{index:02}. "
            f"{layer.instruction[:35]:35} "
            f"{layer.size_mb:8.2f} MB "
            f"{layer.digest[:12]}"
        )


# ============================================================
# 9. Demonstration
# ============================================================

def main() -> None:

    dockerfile = """
    FROM python:3.13-slim
    WORKDIR /app
    COPY requirements.txt .
    RUN pip install -r requirements.txt
    COPY app.py .
    ENV APP_ENV=production
    EXPOSE 8000
    USER 10001
    CMD python app.py
    """

    context = BuildContext(
        files={
            "requirements.txt": b"fastapi==0.115.6\n",
            "app.py": b"print('Application running')\n"
        },
        build_args={
            "PYTHON_VERSION": "3.13"
        }
    )

    cache = LayerCache()
    builder = DockerImageBuilder(cache)

    print("FIRST BUILD")

    first_result = builder.build(
        dockerfile,
        context,
        "learning-api",
        "1.0"
    )

    display_image_report(first_result)

    print("\nSECOND BUILD: CACHE REUSE")

    second_result = builder.build(
        dockerfile,
        context,
        "learning-api",
        "1.0"
    )

    display_image_report(second_result)

    print("\nOPTIMIZATION ANALYSIS")

    findings = ImageOptimizer.analyze(dockerfile)

    if not findings:
        print("No findings detected.")

    for finding in findings:
        print(
            f"[{finding.severity}] {finding.message}\n"
            f"  Recommendation: {finding.recommendation}"
        )

    print("\nMULTI-STAGE BUILD")

    multi = MultiStageBuild()

    multi.add_stage(
        BuildStage(
            name="builder",
            base_image="python:3.13-slim",
            installed_components=["compiler", "build-tools"],
            copied_artifacts=["application"]
        )
    )

    multi.add_stage(
        BuildStage(
            name="runtime",
            base_image="alpine:3.21",
            copied_artifacts=["application", "static-assets"]
        )
    )

    print(
        "Estimated runtime image size: "
        f"{multi.estimate_final_size('runtime') / (1024 * 1024):.2f} MB"
    )

    print("\nVALIDATION TESTS")

    assert first_result.status == BuildStatus.SUCCESS
    assert second_result.cached_layers == second_result.image.layer_count

    invalid_context = BuildContext(
        files={"../secret.txt": b"restricted"}
    )

    invalid_result = builder.build(
        dockerfile,
        invalid_context,
        "invalid-image"
    )

    assert invalid_result.status == BuildStatus.FAILED

    print("All demonstration assertions passed.")


if __name__ == "__main__":
    main()
