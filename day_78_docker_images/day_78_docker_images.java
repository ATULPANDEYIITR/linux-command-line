import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

/**
 * Docker Images: Enterprise image build and governance platform.
 *
 * Java 17 implementation.
 *
 * Features:
 * - Dockerfile parsing
 * - Immutable image layers
 * - Content-addressed caching
 * - Build stages
 * - Build lifecycle
 * - Image manifests
 * - Security policies
 * - Image optimization
 * - Build validation
 * - Merge-free artifact promotion
 *
 * Compile:
 * javac --release 17 Main.java
 *
 * Run:
 * java Main
 */

public class Main {

    // ========================================================
    // 1. Constants and domain exceptions
    // ========================================================

    private static final long MB = 1024L * 1024L;

    private static final Map<String, Long> BASE_IMAGES = Map.of(
        "ubuntu:24.04", 29L * MB,
        "debian:bookworm-slim", 27L * MB,
        "python:3.13-slim", 45L * MB,
        "alpine:3.21", 8L * MB,
        "node:22-alpine", 18L * MB
    );

    private static final Pattern IMAGE_NAME =
        Pattern.compile("[a-z0-9][a-z0-9._/-]*");

    private static final Pattern TAG =
        Pattern.compile("[A-Za-z0-9_.-]+");

    static class BuildException extends RuntimeException {
        BuildException(String message) {
            super(message);
        }
    }

    static class PolicyViolationException extends RuntimeException {
        PolicyViolationException(String message) {
            super(message);
        }
    }

    // ========================================================
    // 2. Instruction domain model
    // ========================================================

    enum InstructionType {
        FROM,
        WORKDIR,
        COPY,
        ADD,
        RUN,
        ENV,
        ARG,
        USER,
        EXPOSE,
        LABEL,
        CMD,
        ENTRYPOINT
    }

    record Instruction(
        InstructionType type,
        String arguments,
        int lineNumber
    ) {
        Instruction {
            Objects.requireNonNull(type);
            Objects.requireNonNull(arguments);

            if (arguments.isBlank()) {
                throw new BuildException(
                    "Instruction arguments cannot be empty."
                );
            }
        }
    }

    // ========================================================
    // 3. Dockerfile parser
    // ========================================================

    static final class DockerfileParser {

        static List<Instruction> parse(String content) {

            if (content == null || content.isBlank()) {
                throw new BuildException("Dockerfile is empty.");
            }

            List<Instruction> instructions = new ArrayList<>();

            String[] lines = content.split("\\R");

            for (int index = 0; index < lines.length; index++) {

                String line = lines[index].trim();

                if (line.isEmpty() || line.startsWith("#")) {
                    continue;
                }

                String[] parts = line.split("\\s+", 2);

                if (parts.length != 2) {
                    throw new BuildException(
                        "Invalid Dockerfile line: " + (index + 1)
                    );
                }

                InstructionType type;

                try {
                    type = InstructionType.valueOf(
                        parts[0].toUpperCase()
                    );
                } catch (IllegalArgumentException exception) {
                    throw new BuildException(
                        "Unsupported instruction: " + parts[0]
                    );
                }

                instructions.add(
                    new Instruction(
                        type,
                        parts[1].trim(),
                        index + 1
                    )
                );
            }

            if (instructions.isEmpty()) {
                throw new BuildException(
                    "No valid instructions found."
                );
            }

            if (instructions.getFirst().type() != InstructionType.FROM) {
                throw new BuildException(
                    "Dockerfile must begin with FROM."
                );
            }

            return List.copyOf(instructions);
        }
    }

    // ========================================================
    // 4. Build context
    // ========================================================

    static final class BuildContext {

        private final Map<String, byte[]> files;
        private final Map<String, String> arguments;

        BuildContext(
            Map<String, byte[]> inputFiles,
            Map<String, String> buildArguments
        ) {
            this.files = new LinkedHashMap<>();
            this.arguments = new HashMap<>(buildArguments);

            inputFiles.forEach((path, content) -> {

                validatePath(path);

                if (content == null) {
                    throw new BuildException(
                        "Null file content: " + path
                    );
                }

                this.files.put(path, content.clone());
            });
        }

        private static void validatePath(String path) {
            if (
                path == null ||
                path.isBlank() ||
                path.startsWith("/") ||
                List.of(path.split("/")).contains("..")
            ) {
                throw new BuildException(
                    "Unsafe build-context path: " + path
                );
            }
        }

        boolean contains(String path) {
            return files.containsKey(path);
        }

        long fileSize(String path) {
            byte[] content = files.get(path);

            if (content == null) {
                throw new BuildException(
                    "Build-context file missing: " + path
                );
            }

            return content.length;
        }

        String fingerprint() {
            StringBuilder content = new StringBuilder();

            files.entrySet().stream()
                .sorted(Map.Entry.comparingByKey())
                .forEach(entry -> content
                    .append(entry.getKey())
                    .append('\0')
                    .append(sha256(entry.getValue()))
                    .append('\0')
                );

            return sha256(
                content.toString().getBytes(StandardCharsets.UTF_8)
            );
        }

        Map<String, String> arguments() {
            return Collections.unmodifiableMap(arguments);
        }
    }

    // ========================================================
    // 5. Cryptographic digest utility
    // ========================================================

    static String sha256(byte[] value) {
        try {
            MessageDigest digest =
                MessageDigest.getInstance("SHA-256");

            byte[] hash = digest.digest(value);

            StringBuilder output = new StringBuilder();

            for (byte item : hash) {
                output.append(
                    String.format("%02x", item & 0xff)
                );
            }

            return output.toString();

        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException(
                "SHA-256 is unavailable.",
                exception
            );
        }
    }

    static String sha256(String value) {
        return sha256(
            value.getBytes(StandardCharsets.UTF_8)
        );
    }

    // ========================================================
    // 6. Immutable image layer
    // ========================================================

    record ImageLayer(
        String digest,
        String instruction,
        long sizeBytes,
        Optional<String> parentDigest,
        Instant createdAt
    ) {
        ImageLayer {
            Objects.requireNonNull(digest);
            Objects.requireNonNull(instruction);
            Objects.requireNonNull(parentDigest);
            Objects.requireNonNull(createdAt);

            if (sizeBytes < 0) {
                throw new IllegalArgumentException(
                    "Layer size cannot be negative."
                );
            }
        }
    }

    // ========================================================
    // 7. Image model
    // ========================================================

    static final class DockerImage {

        private final String name;
        private final String tag;
        private final String architecture;

        private final List<ImageLayer> layers =
            new ArrayList<>();

        DockerImage(
            String name,
            String tag,
            String architecture
        ) {
            if (!IMAGE_NAME.matcher(name).matches()) {
                throw new BuildException("Invalid image name.");
            }

            if (!TAG.matcher(tag).matches()) {
                throw new BuildException("Invalid image tag.");
            }

            this.name = name;
            this.tag = tag;
            this.architecture = architecture;
        }

        void addLayer(ImageLayer layer) {
            layers.add(Objects.requireNonNull(layer));
        }

        long totalSize() {
            return layers.stream()
                .mapToLong(ImageLayer::sizeBytes)
                .sum();
        }

        double totalSizeMB() {
            return totalSize() / (double) MB;
        }

        String imageId() {
            String content = layers.stream()
                .map(ImageLayer::digest)
                .collect(Collectors.joining());

            return sha256(content);
        }

        List<ImageLayer> layers() {
            return List.copyOf(layers);
        }

        String name() {
            return name;
        }

        String tag() {
            return tag;
        }

        String architecture() {
            return architecture;
        }

        void printManifest() {
            System.out.println("\nIMAGE MANIFEST");
            System.out.println("----------------------------------");

            System.out.println("Name: " + name);
            System.out.println("Tag: " + tag);
            System.out.println("Image ID: " + imageId());
            System.out.println("Architecture: " + architecture);
            System.out.println("Layers: " + layers.size());

            System.out.printf(
                "Size: %.2f MB%n",
                totalSizeMB()
            );

            for (int index = 0; index < layers.size(); index++) {
                ImageLayer layer = layers.get(index);

                System.out.printf(
                    "%02d. %-25s %.2f MB%n",
                    index + 1,
                    layer.instruction(),
                    layer.sizeBytes() / (double) MB
                );
            }
        }
    }

    // ========================================================
    // 8. Content-addressed layer cache
    // ========================================================

    static final class LayerCache {

        private final Map<String, ImageLayer> layers =
            new HashMap<>();

        private long hits;
        private long misses;

        Optional<ImageLayer> find(String key) {

            ImageLayer layer = layers.get(key);

            if (layer == null) {
                misses++;
                return Optional.empty();
            }

            hits++;

            return Optional.of(layer);
        }

        void store(String key, ImageLayer layer) {
            layers.put(key, layer);
        }

        long hits() {
            return hits;
        }

        long misses() {
            return misses;
        }

        int size() {
            return layers.size();
        }

        double hitRate() {
            long total = hits + misses;

            return total == 0 ? 0 : hits / (double) total;
        }
    }

    // ========================================================
    // 9. Build lifecycle
    // ========================================================

    enum BuildStatus {
        PENDING,
        RUNNING,
        SUCCEEDED,
        FAILED
    }

    static final class BuildJob {

        private BuildStatus status = BuildStatus.PENDING;
        private final List<String> events = new ArrayList<>();

        void transition(BuildStatus next) {

            boolean allowed = switch (status) {
                case PENDING -> next == BuildStatus.RUNNING;
                case RUNNING ->
                    next == BuildStatus.SUCCEEDED ||
                    next == BuildStatus.FAILED;
                case SUCCEEDED, FAILED -> false;
            };

            if (!allowed) {
                throw new BuildException(
                    "Invalid build transition: "
                    + status + " -> " + next
                );
            }

            status = next;
            events.add(
                Instant.now() + " " + next
            );
        }

        BuildStatus status() {
            return status;
        }

        List<String> events() {
            return List.copyOf(events);
        }
    }

    record BuildResult(
        DockerImage image,
        int createdLayers,
        int cachedLayers,
        double durationMilliseconds
    ) {}

    // ========================================================
    // 10. Build service
    // ========================================================

    static final class DockerBuildService {

        private final LayerCache cache = new LayerCache();

        private long estimateRunSize(String command) {

            String normalized = command.toLowerCase();

            if (normalized.contains("apt-get install")) {
                return 25 * MB;
            }

            if (normalized.contains("pip install")) {
                return 15 * MB;
            }

            if (normalized.contains("npm install")) {
                return 20 * MB;
            }

            if (normalized.contains("apk add")) {
                return 8 * MB;
            }

            return MB;
        }

        BuildResult build(
            String dockerfile,
            BuildContext context,
            String imageName,
            String tag
        ) {
            long start = System.nanoTime();

            BuildJob job = new BuildJob();
            job.transition(BuildStatus.RUNNING);

            try {
                List<Instruction> instructions =
                    DockerfileParser.parse(dockerfile);

                DockerImage image = new DockerImage(
                    imageName,
                    tag,
                    "linux/amd64"
                );

                String contextHash = context.fingerprint();

                Optional<String> parentDigest =
                    Optional.empty();

                int created = 0;
                int cached = 0;

                for (int index = 0;
                     index < instructions.size();
                     index++) {

                    Instruction instruction =
                        instructions.get(index);

                    long size = 0;

                    switch (instruction.type()) {

                        case FROM: {
                            String base = instruction.arguments()
                                .split("\\s+")[0];

                            Long baseSize = BASE_IMAGES.get(base);

                            if (baseSize == null) {
                                throw new BuildException(
                                    "Unknown base image: " + base
                                );
                            }

                            if (index != 0) {
                                throw new BuildException(
                                    "Additional stages are not supported "
                                    + "by this single-stage service."
                                );
                            }

                            size = baseSize;
                            break;
                        }

                        case COPY:
                        case ADD: {
                            String[] parts =
                                instruction.arguments().split("\\s+");

                            if (parts.length < 2) {
                                throw new BuildException(
                                    "COPY and ADD need two arguments."
                                );
                            }

                            size = context.fileSize(parts[0]);
                            break;
                        }

                        case RUN:
                            size = estimateRunSize(
                                instruction.arguments()
                            );
                            break;

                        case WORKDIR:
                            if (
                                instruction.arguments()
                                    .contains("..")
                            ) {
                                throw new BuildException(
                                    "Unsafe working directory."
                                );
                            }
                            break;

                        case ENV:
                            if (
                                !instruction.arguments().contains("=")
                            ) {
                                throw new BuildException(
                                    "Invalid ENV instruction."
                                );
                            }
                            break;

                        case USER:
                            if (instruction.arguments().isBlank()) {
                                throw new BuildException(
                                    "USER cannot be empty."
                                );
                            }
                            break;

                        case EXPOSE: {
                            String portText =
                                instruction.arguments().split("/")[0];

                            int port;

                            try {
                                port = Integer.parseInt(portText);
                            } catch (NumberFormatException exception) {
                                throw new BuildException(
                                    "Invalid exposed port."
                                );
                            }

                            if (port < 1 || port > 65535) {
                                throw new BuildException(
                                    "Port outside valid range."
                                );
                            }
                            break;
                        }

                        case ARG:
                        case LABEL:
                        case CMD:
                        case ENTRYPOINT:
                            break;
                    }

                    String key = sha256(
                        instruction.type()
                        + ":"
                        + instruction.arguments()
                        + ":"
                        + parentDigest.orElse("ROOT")
                        + ":"
                        + contextHash
                        + ":"
                        + context.arguments()
                    );

                    Optional<ImageLayer> existing =
                        cache.find(key);

                    ImageLayer layer;

                    if (existing.isPresent()) {
                        layer = existing.get();
                        cached++;

                    } else {
                        String digest = sha256(
                            key + ":" + size
                        );

                        layer = new ImageLayer(
                            digest,
                            instruction.type()
                                + " "
                                + instruction.arguments(),
                            size,
                            parentDigest,
                            Instant.now()
                        );

                        cache.store(key, layer);
                        created++;
                    }

                    image.addLayer(layer);
                    parentDigest = Optional.of(layer.digest());
                }

                job.transition(BuildStatus.SUCCEEDED);

                double duration =
                    (System.nanoTime() - start) / 1_000_000.0;

                return new BuildResult(
                    image,
                    created,
                    cached,
                    duration
                );

            } catch (RuntimeException exception) {
                job.transition(BuildStatus.FAILED);
                throw exception;
            }
        }

        LayerCache cache() {
            return cache;
        }
    }

    // ========================================================
    // 11. Enterprise image policies
    // ========================================================

    enum PolicyRule {
        NON_ROOT_EXECUTION,
        PINNED_BASE_IMAGE,
        MAXIMUM_SIZE,
        MAXIMUM_LAYERS
    }

    record PolicyFinding(
        PolicyRule rule,
        String severity,
        String description,
        String remediation
    ) {}

    record ImagePolicy(
        long maximumSizeBytes,
        int maximumLayers,
        boolean requireNonRoot,
        boolean requirePinnedBase
    ) {
        ImagePolicy {
            if (maximumSizeBytes <= 0 || maximumLayers <= 0) {
                throw new IllegalArgumentException(
                    "Policy limits must be positive."
                );
            }
        }
    }

    static final class PolicyEvaluator {

        private final ImagePolicy policy;

        PolicyEvaluator(ImagePolicy policy) {
            this.policy = policy;
        }

        List<PolicyFinding> evaluate(
            DockerImage image,
            List<Instruction> instructions
        ) {
            List<PolicyFinding> findings = new ArrayList<>();

            boolean nonRoot = instructions.stream()
                .filter(item -> item.type() == InstructionType.USER)
                .anyMatch(item ->
                    !item.arguments().equalsIgnoreCase("root") &&
                    !item.arguments().equals("0")
                );

            boolean pinnedBase = instructions.stream()
                .filter(item -> item.type() == InstructionType.FROM)
                .noneMatch(item ->
                    item.arguments().split("\\s+")[0]
                        .endsWith(":latest")
                );

            if (policy.requireNonRoot() && !nonRoot) {
                findings.add(new PolicyFinding(
                    PolicyRule.NON_ROOT_EXECUTION,
                    "HIGH",
                    "No explicit non-root execution user.",
                    "Configure a dedicated application user."
                ));
            }

            if (policy.requirePinnedBase() && !pinnedBase) {
                findings.add(new PolicyFinding(
                    PolicyRule.PINNED_BASE_IMAGE,
                    "MEDIUM",
                    "A mutable latest tag is used.",
                    "Use a controlled version or immutable digest."
                ));
            }

            if (image.totalSize() > policy.maximumSizeBytes()) {
                findings.add(new PolicyFinding(
                    PolicyRule.MAXIMUM_SIZE,
                    "HIGH",
                    "Image exceeds the permitted size.",
                    "Reduce unnecessary packages and build artifacts."
                ));
            }

            if (image.layers().size() > policy.maximumLayers()) {
                findings.add(new PolicyFinding(
                    PolicyRule.MAXIMUM_LAYERS,
                    "MEDIUM",
                    "Image exceeds the permitted layer count.",
                    "Review Dockerfile structure."
                ));
            }

            return List.copyOf(findings);
        }
    }

    // ========================================================
    // 12. Multi-stage build model
    // ========================================================

    record BuildStage(
        String name,
        String baseImage,
        Set<String> artifacts
    ) {
        BuildStage {
            if (name == null || name.isBlank()) {
                throw new BuildException("Stage name is required.");
            }

            artifacts = Set.copyOf(artifacts);
        }
    }

    static final class MultiStageBuild {

        private final Map<String, BuildStage> stages =
            new LinkedHashMap<>();

        private final Map<String, Long> artifactSizes = Map.of(
            "application", 5 * MB,
            "binary", 12 * MB,
            "assets", 2 * MB
        );

        void addStage(BuildStage stage) {

            if (stages.containsKey(stage.name())) {
                throw new BuildException(
                    "Duplicate stage: " + stage.name()
                );
            }

            if (!BASE_IMAGES.containsKey(stage.baseImage())) {
                throw new BuildException(
                    "Unknown base image: " + stage.baseImage()
                );
            }

            stages.put(stage.name(), stage);
        }

        long estimateRuntimeSize(String stageName) {

            BuildStage stage = stages.get(stageName);

            if (stage == null) {
                throw new BuildException("Stage does not exist.");
            }

            long total = BASE_IMAGES.get(stage.baseImage());

            for (String artifact : stage.artifacts()) {

                Long size = artifactSizes.get(artifact);

                if (size == null) {
                    throw new BuildException(
                        "Unknown artifact: " + artifact
                    );
                }

                total += size;
            }

            return total;
        }
    }

    // ========================================================
    // 13. Application demonstration
    // ========================================================

    public static void main(String[] args) {

        String dockerfile = """
            FROM python:3.13-slim
            WORKDIR /app
            COPY requirements.txt .
            RUN pip install -r requirements.txt
            COPY app.py .
            ENV APP_ENV=production
            EXPOSE 8000
            USER 10001
            CMD python app.py
            """;

        Map<String, byte[]> files = new HashMap<>();

        files.put(
            "requirements.txt",
            "fastapi==0.115.6\n".getBytes(StandardCharsets.UTF_8)
        );

        files.put(
            "app.py",
            "print('Application running')\n"
                .getBytes(StandardCharsets.UTF_8)
        );

        BuildContext context = new BuildContext(
            files,
            Map.of("PYTHON_VERSION", "3.13")
        );

        DockerBuildService service = new DockerBuildService();

        System.out.println("FIRST BUILD");

        BuildResult first = service.build(
            dockerfile,
            context,
            "enterprise-api",
            "1.0"
        );

        first.image().printManifest();

        System.out.println("\nSECOND BUILD");

        BuildResult second = service.build(
            dockerfile,
            context,
            "enterprise-api",
            "1.0"
        );

        System.out.println(
            "Cached layers: " + second.cachedLayers()
        );

        System.out.println(
            "Created layers: " + second.createdLayers()
        );

        System.out.println("\nIMAGE GOVERNANCE");

        ImagePolicy policy = new ImagePolicy(
            150 * MB,
            15,
            true,
            true
        );

        List<PolicyFinding> findings =
            new PolicyEvaluator(policy).evaluate(
                first.image(),
                DockerfileParser.parse(dockerfile)
            );

        if (findings.isEmpty()) {
            System.out.println("No policy violations.");
        }

        findings.forEach(finding -> System.out.println(
            "[" + finding.severity() + "] "
            + finding.rule() + ": "
            + finding.description()
            + "\nRemediation: "
            + finding.remediation()
        ));

        System.out.println("\nMULTI-STAGE BUILD");

        MultiStageBuild multiStage = new MultiStageBuild();

        multiStage.addStage(
            new BuildStage(
                "builder",
                "python:3.13-slim",
                Set.of("application", "binary")
            )
        );

        multiStage.addStage(
            new BuildStage(
                "runtime",
                "alpine:3.21",
                Set.of("application", "assets")
            )
        );

        System.out.printf(
            "Runtime image estimate: %.2f MB%n",
            multiStage.estimateRuntimeSize("runtime") / (double) MB
        );

        System.out.println("\nCACHE METRICS");

        System.out.println(
            "Entries: " + service.cache().size()
        );

        System.out.println(
            "Hits: " + service.cache().hits()
        );

        System.out.println(
            "Misses: " + service.cache().misses()
        );

        System.out.printf(
            "Hit rate: %.2f%%%n",
            service.cache().hitRate() * 100
        );

        System.out.println("\nVALIDATION");

        if (!first.image().imageId().equals(second.image().imageId())) {
            throw new IllegalStateException(
                "Repeated builds produced different image identifiers."
            );
        }

        if (
            second.cachedLayers() !=
            second.image().layers().size()
        ) {
            throw new IllegalStateException(
                "Layer cache validation failed."
            );
        }

        System.out.println("All validation checks passed.");
    }
}
