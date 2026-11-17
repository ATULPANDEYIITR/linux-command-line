#include <algorithm>
#include <chrono>
#include <cstdint>
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

/*
 * Docker Images: Repository-independent image governance engine.
 *
 * C++17 implementation covering:
 * - Dockerfile instructions
 * - Image layers
 * - Layer dependency chains
 * - Content-derived cache keys
 * - Build context validation
 * - Image size estimation
 * - Image optimization
 * - Multi-stage builds
 * - Image security policies
 * - Build eligibility evaluation
 *
 * Compile:
 * g++ -std=c++17 -O2 -Wall -Wextra -pedantic docker_images.cpp -o docker_images
 *
 * Run:
 * ./docker_images
 */

namespace docker {

// ============================================================
// 1. Domain types
// ============================================================

using Size = std::uint64_t;

constexpr Size MB = 1024ULL * 1024ULL;

enum class InstructionType {
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
};

enum class Severity {
    LOW,
    MEDIUM,
    HIGH,
    CRITICAL
};

std::string toString(InstructionType type) {
    switch (type) {
        case InstructionType::FROM: return "FROM";
        case InstructionType::WORKDIR: return "WORKDIR";
        case InstructionType::COPY: return "COPY";
        case InstructionType::ADD: return "ADD";
        case InstructionType::RUN: return "RUN";
        case InstructionType::ENV: return "ENV";
        case InstructionType::ARG: return "ARG";
        case InstructionType::USER: return "USER";
        case InstructionType::EXPOSE: return "EXPOSE";
        case InstructionType::LABEL: return "LABEL";
        case InstructionType::CMD: return "CMD";
        case InstructionType::ENTRYPOINT: return "ENTRYPOINT";
    }

    throw std::logic_error("Unknown instruction.");
}

struct Instruction {
    InstructionType type;
    std::string arguments;
    std::size_t lineNumber;
};

struct Layer {
    std::string digest;
    std::string instruction;
    Size sizeBytes = 0;
    std::optional<std::string> parentDigest;
    bool cached = false;
};

struct Finding {
    Severity severity;
    std::string rule;
    std::string message;
    std::string recommendation;
};

struct BuildStatistics {
    std::size_t createdLayers = 0;
    std::size_t cachedLayers = 0;
    std::size_t failedChecks = 0;
};

class DockerException : public std::runtime_error {
public:
    explicit DockerException(const std::string& message)
        : std::runtime_error(message) {}
};

// ============================================================
// 2. Utility functions
// ============================================================

std::string trim(const std::string& input) {
    const auto first = input.find_first_not_of(" \t\r\n");

    if (first == std::string::npos) {
        return "";
    }

    const auto last = input.find_last_not_of(" \t\r\n");

    return input.substr(first, last - first + 1);
}

std::vector<std::string> splitWords(const std::string& input) {
    std::istringstream stream(input);
    std::vector<std::string> result;
    std::string word;

    while (stream >> word) {
        result.push_back(word);
    }

    return result;
}

std::string pseudoDigest(const std::string& input) {
    /*
     * FNV-1a is used only to demonstrate deterministic cache
     * identifiers. It is NOT a cryptographic image digest.
     * Production registries use cryptographic content digests.
     */

    std::uint64_t hash = 14695981039346656037ULL;

    for (unsigned char character : input) {
        hash ^= character;
        hash *= 1099511628211ULL;
    }

    std::ostringstream output;

    output << std::hex
           << std::setfill('0')
           << std::setw(16)
           << hash;

    return output.str();
}

std::string join(
    const std::vector<std::string>& values,
    const std::string& separator
) {
    std::ostringstream output;

    for (std::size_t i = 0; i < values.size(); ++i) {
        if (i > 0) {
            output << separator;
        }

        output << values[i];
    }

    return output.str();
}

// ============================================================
// 3. Base image registry
// ============================================================

class BaseImageRegistry {

private:
    std::map<std::string, Size> images = {
        {"ubuntu:24.04", 29 * MB},
        {"debian:bookworm-slim", 27 * MB},
        {"python:3.13-slim", 45 * MB},
        {"alpine:3.21", 8 * MB},
        {"node:22-alpine", 18 * MB}
    };

public:
    Size getSize(const std::string& image) const {
        auto iterator = images.find(image);

        if (iterator == images.end()) {
            throw DockerException(
                "Unsupported base image: " + image
            );
        }

        return iterator->second;
    }

    bool contains(const std::string& image) const {
        return images.find(image) != images.end();
    }
};

// ============================================================
// 4. Dockerfile parser
// ============================================================

class DockerfileParser {

private:
    static InstructionType identify(const std::string& keyword) {
        static const std::map<std::string, InstructionType> mapping = {
            {"FROM", InstructionType::FROM},
            {"WORKDIR", InstructionType::WORKDIR},
            {"COPY", InstructionType::COPY},
            {"ADD", InstructionType::ADD},
            {"RUN", InstructionType::RUN},
            {"ENV", InstructionType::ENV},
            {"ARG", InstructionType::ARG},
            {"USER", InstructionType::USER},
            {"EXPOSE", InstructionType::EXPOSE},
            {"LABEL", InstructionType::LABEL},
            {"CMD", InstructionType::CMD},
            {"ENTRYPOINT", InstructionType::ENTRYPOINT}
        };

        auto iterator = mapping.find(keyword);

        if (iterator == mapping.end()) {
            throw DockerException(
                "Unsupported Dockerfile instruction: " + keyword
            );
        }

        return iterator->second;
    }

public:
    static std::vector<Instruction> parse(
        const std::string& dockerfile
    ) {
        std::istringstream input(dockerfile);
        std::vector<Instruction> instructions;

        std::string line;
        std::size_t lineNumber = 0;

        while (std::getline(input, line)) {
            ++lineNumber;
            line = trim(line);

            if (line.empty() || line[0] == '#') {
                continue;
            }

            std::istringstream parser(line);

            std::string keyword;
            parser >> keyword;

            std::string arguments;
            std::getline(parser, arguments);

            arguments = trim(arguments);

            if (arguments.empty()) {
                throw DockerException(
                    "Missing arguments on line " +
                    std::to_string(lineNumber)
                );
            }

            std::transform(
                keyword.begin(),
                keyword.end(),
                keyword.begin(),
                [](unsigned char c) {
                    return static_cast<char>(std::toupper(c));
                }
            );

            instructions.push_back({
                identify(keyword),
                arguments,
                lineNumber
            });
        }

        if (instructions.empty()) {
            throw DockerException("Dockerfile is empty.");
        }

        if (instructions.front().type != InstructionType::FROM) {
            throw DockerException(
                "The first instruction must be FROM."
            );
        }

        return instructions;
    }
};

// ============================================================
// 5. Build context
// ============================================================

class BuildContext {

private:
    std::map<std::string, std::string> files;

public:
    void addFile(
        const std::string& path,
        const std::string& content
    ) {
        if (
            path.empty() ||
            path.front() == '/' ||
            path.find("..") != std::string::npos
        ) {
            throw DockerException(
                "Unsafe build-context path: " + path
            );
        }

        files[path] = content;
    }

    bool hasFile(const std::string& path) const {
        return files.find(path) != files.end();
    }

    Size getFileSize(const std::string& path) const {
        auto iterator = files.find(path);

        if (iterator == files.end()) {
            throw DockerException(
                "Build-context file not found: " + path
            );
        }

        return static_cast<Size>(iterator->second.size());
    }

    std::string fingerprint() const {
        std::ostringstream content;

        for (const auto& [path, value] : files) {
            content << path
                    << '\0'
                    << value
                    << '\0';
        }

        return pseudoDigest(content.str());
    }
};

// ============================================================
// 6. Image model
// ============================================================

class DockerImage {

private:
    std::string name;
    std::string tag;
    std::vector<Layer> layers;

public:
    DockerImage(std::string imageName, std::string imageTag)
        : name(std::move(imageName)),
          tag(std::move(imageTag)) {}

    void addLayer(const Layer& layer) {
        layers.push_back(layer);
    }

    Size totalSize() const {
        Size total = 0;

        for (const auto& layer : layers) {
            total += layer.sizeBytes;
        }

        return total;
    }

    const std::vector<Layer>& getLayers() const {
        return layers;
    }

    std::string getName() const {
        return name;
    }

    std::string getTag() const {
        return tag;
    }

    std::string imageId() const {
        std::string content;

        for (const auto& layer : layers) {
            content += layer.digest;
        }

        return pseudoDigest(content);
    }

    void print() const {
        std::cout << "\nIMAGE REPORT\n";
        std::cout << "----------------------------------------\n";

        std::cout << "Image: "
                  << name << ":" << tag << "\n";

        std::cout << "Image ID: "
                  << imageId() << "\n";

        std::cout << "Layers: "
                  << layers.size() << "\n";

        std::cout << "Total size: "
                  << std::fixed
                  << std::setprecision(2)
                  << static_cast<double>(totalSize()) / MB
                  << " MB\n";

        for (std::size_t i = 0; i < layers.size(); ++i) {
            std::cout << i + 1
                      << ". "
                      << layers[i].instruction
                      << " | "
                      << static_cast<double>(
                          layers[i].sizeBytes
                      ) / MB
                      << " MB"
                      << (layers[i].cached ? " [CACHE]" : "")
                      << "\n";
        }
    }
};

// ============================================================
// 7. Layer cache
// ============================================================

class LayerCache {

private:
    std::unordered_map<std::string, Layer> entries;

public:
    std::optional<Layer> find(
        const std::string& key
    ) const {
        auto iterator = entries.find(key);

        if (iterator == entries.end()) {
            return std::nullopt;
        }

        return iterator->second;
    }

    void store(
        const std::string& key,
        const Layer& layer
    ) {
        entries[key] = layer;
    }

    std::size_t size() const {
        return entries.size();
    }
};

// ============================================================
// 8. Image build engine
// ============================================================

class DockerBuilder {

private:
    BaseImageRegistry registry;
    LayerCache cache;

    Size estimateRunSize(const std::string& command) const {
        if (command.find("apt-get install") != std::string::npos) {
            return 25 * MB;
        }

        if (command.find("pip install") != std::string::npos) {
            return 15 * MB;
        }

        if (command.find("npm install") != std::string::npos) {
            return 20 * MB;
        }

        if (command.find("apk add") != std::string::npos) {
            return 8 * MB;
        }

        return MB;
    }

    static std::string cacheKey(
        const Instruction& instruction,
        const std::optional<std::string>& parent,
        const std::string& contextHash
    ) {
        std::string parentValue =
            parent.has_value() ? parent.value() : "ROOT";

        return pseudoDigest(
            toString(instruction.type)
            + ":"
            + instruction.arguments
            + ":"
            + parentValue
            + ":"
            + contextHash
        );
    }

public:
    struct Result {
        DockerImage image;
        BuildStatistics statistics;

        Result(
            DockerImage value,
            BuildStatistics stats
        )
            : image(std::move(value)),
              statistics(stats) {}
    };

    Result build(
        const std::string& dockerfile,
        const BuildContext& context,
        const std::string& imageName,
        const std::string& tag
    ) {
        if (imageName.empty() || tag.empty()) {
            throw DockerException(
                "Image name and tag are required."
            );
        }

        const auto instructions =
            DockerfileParser::parse(dockerfile);

        DockerImage image(imageName, tag);

        BuildStatistics statistics;

        std::optional<std::string> parentDigest;

        const std::string contextHash =
            context.fingerprint();

        std::string currentUser = "root";

        for (const auto& instruction : instructions) {

            Size layerSize = 0;

            switch (instruction.type) {

                case InstructionType::FROM: {
                    const auto parts =
                        splitWords(instruction.arguments);

                    if (parts.empty()) {
                        throw DockerException(
                            "Missing base image."
                        );
                    }

                    if (image.getLayers().size() > 0) {
                        throw DockerException(
                            "This demonstration builder supports "
                            "one stage at a time."
                        );
                    }

                    layerSize = registry.getSize(parts[0]);
                    break;
                }

                case InstructionType::COPY:
                case InstructionType::ADD: {
                    const auto parts =
                        splitWords(instruction.arguments);

                    if (parts.size() < 2) {
                        throw DockerException(
                            "COPY and ADD need source and destination."
                        );
                    }

                    layerSize = context.getFileSize(parts[0]);
                    break;
                }

                case InstructionType::RUN:
                    layerSize =
                        estimateRunSize(instruction.arguments);
                    break;

                case InstructionType::WORKDIR:
                    if (
                        instruction.arguments.find("..") !=
                        std::string::npos
                    ) {
                        throw DockerException(
                            "Unsafe WORKDIR path."
                        );
                    }
                    break;

                case InstructionType::USER:
                    currentUser = instruction.arguments;
                    break;

                case InstructionType::ENV:
                    if (
                        instruction.arguments.find('=') ==
                        std::string::npos
                    ) {
                        throw DockerException(
                            "ENV requires KEY=VALUE."
                        );
                    }
                    break;

                case InstructionType::ARG: {
                    const auto parts =
                        splitWords(instruction.arguments);

                    if (
                        parts.empty() ||
                        parts[0].find_first_not_of(
                            "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                            "abcdefghijklmnopqrstuvwxyz"
                            "0123456789_"
                        ) != std::string::npos
                    ) {
                        throw DockerException(
                            "Invalid ARG declaration."
                        );
                    }
                    break;
                }

                case InstructionType::EXPOSE: {
                    const auto parts =
                        splitWords(instruction.arguments);

                    if (parts.empty()) {
                        throw DockerException("Missing port.");
                    }

                    int port = 0;

                    try {
                        port = std::stoi(parts[0]);
                    } catch (...) {
                        throw DockerException("Invalid port.");
                    }

                    if (port < 1 || port > 65535) {
                        throw DockerException(
                            "Port outside valid range."
                        );
                    }
                    break;
                }

                default:
                    break;
            }

            const std::string key = cacheKey(
                instruction,
                parentDigest,
                contextHash
            );

            auto cached = cache.find(key);

            Layer layer;

            if (cached.has_value()) {
                layer = cached.value();
                layer.cached = true;
                ++statistics.cachedLayers;
            } else {
                const std::string digest = pseudoDigest(
                    key + ":" +
                    std::to_string(layerSize) +
                    ":" + currentUser
                );

                layer = {
                    digest,
                    toString(instruction.type)
                        + " "
                        + instruction.arguments,
                    layerSize,
                    parentDigest,
                    false
                };

                cache.store(key, layer);
                ++statistics.createdLayers;
            }

            image.addLayer(layer);
            parentDigest = layer.digest;
        }

        return Result(image, statistics);
    }

    std::size_t cacheSize() const {
        return cache.size();
    }
};

// ============================================================
// 9. Governance and optimization policies
// ============================================================

class ImageGovernance {

public:
    static std::vector<Finding> evaluate(
        const DockerImage& image,
        const std::vector<Instruction>& instructions
    ) {
        std::vector<Finding> findings;

        bool hasNonRootUser = false;
        bool usesLatest = false;

        for (const auto& item : instructions) {

            if (item.type == InstructionType::USER) {
                hasNonRootUser =
                    item.arguments != "root" &&
                    item.arguments != "0";
            }

            if (
                item.type == InstructionType::FROM &&
                item.arguments.find(":latest") != std::string::npos
            ) {
                usesLatest = true;
            }
        }

        if (!hasNonRootUser) {
            findings.push_back({
                Severity::HIGH,
                "NON_ROOT_USER",
                "No explicit non-root execution user.",
                "Add a dedicated USER instruction."
            });
        }

        if (usesLatest) {
            findings.push_back({
                Severity::MEDIUM,
                "MUTABLE_BASE_IMAGE",
                "The image uses a latest tag.",
                "Pin the base image to a controlled version or digest."
            });
        }

        if (image.getLayers().size() > 20) {
            findings.push_back({
                Severity::MEDIUM,
                "EXCESSIVE_LAYERS",
                "The image has more than twenty layers.",
                "Review instruction grouping and build structure."
            });
        }

        if (image.totalSize() > 500 * MB) {
            findings.push_back({
                Severity::HIGH,
                "IMAGE_SIZE",
                "Image exceeds the 500 MB policy.",
                "Review base images, dependencies and build artifacts."
            });
        }

        return findings;
    }
};

// ============================================================
// 10. Multi-stage build model
// ============================================================

struct BuildStage {
    std::string name;
    std::string baseImage;
    std::vector<std::string> artifacts;
};

class MultiStageBuild {

private:
    BaseImageRegistry registry;
    std::map<std::string, BuildStage> stages;

public:
    void addStage(const BuildStage& stage) {
        if (stages.count(stage.name)) {
            throw DockerException(
                "Duplicate build-stage name."
            );
        }

        registry.getSize(stage.baseImage);
        stages.emplace(stage.name, stage);
    }

    Size estimateFinalSize(
        const std::string& stageName
    ) const {
        auto iterator = stages.find(stageName);

        if (iterator == stages.end()) {
            throw DockerException(
                "Unknown build stage."
            );
        }

        const auto& stage = iterator->second;

        Size total = registry.getSize(stage.baseImage);

        const std::map<std::string, Size> artifactSizes = {
            {"application", 5 * MB},
            {"binary", 12 * MB},
            {"assets", 2 * MB}
        };

        for (const auto& artifact : stage.artifacts) {
            auto size = artifactSizes.find(artifact);

            if (size == artifactSizes.end()) {
                throw DockerException(
                    "Unknown runtime artifact: " + artifact
                );
            }

            total += size->second;
        }

        return total;
    }
};

// ============================================================
// 11. Main demonstration
// ============================================================

} // namespace docker

int main() {

    using namespace docker;

    try {

        const std::string dockerfile = R"(
FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app.py .
ENV APP_ENV=production
EXPOSE 8000
USER 10001
CMD python app.py
)";

        BuildContext context;

        context.addFile(
            "requirements.txt",
            "fastapi==0.115.6\n"
        );

        context.addFile(
            "app.py",
            "print('Application started')\n"
        );

        DockerBuilder builder;

        std::cout << "FIRST IMAGE BUILD\n";

        auto first = builder.build(
            dockerfile,
            context,
            "learning-api",
            "1.0"
        );

        first.image.print();

        std::cout << "\nBUILD STATISTICS\n";

        std::cout
            << "Created: "
            << first.statistics.createdLayers
            << "\n";

        std::cout
            << "Cached: "
            << first.statistics.cachedLayers
            << "\n";

        std::cout << "\nSECOND BUILD\n";

        auto second = builder.build(
            dockerfile,
            context,
            "learning-api",
            "1.0"
        );

        second.image.print();

        std::cout
            << "Cache entries: "
            << builder.cacheSize()
            << "\n";

        std::cout << "\nIMAGE GOVERNANCE\n";

        const auto instructions =
            DockerfileParser::parse(dockerfile);

        const auto findings = ImageGovernance::evaluate(
            first.image,
            instructions
        );

        if (findings.empty()) {
            std::cout << "No governance findings.\n";
        }

        for (const auto& finding : findings) {
            std::cout
                << "[" << finding.rule << "] "
                << finding.message
                << "\nRecommendation: "
                << finding.recommendation
                << "\n";
        }

        std::cout << "\nMULTI-STAGE BUILD\n";

        MultiStageBuild multi;

        multi.addStage({
            "builder",
            "python:3.13-slim",
            {"application", "binary"}
        });

        multi.addStage({
            "runtime",
            "alpine:3.21",
            {"application", "assets"}
        });

        std::cout
            << "Runtime image estimate: "
            << static_cast<double>(
                multi.estimateFinalSize("runtime")
            ) / MB
            << " MB\n";

        std::cout << "\nVALIDATION TESTS\n";

        if (
            first.image.getLayers().size() !=
            second.image.getLayers().size()
        ) {
            throw DockerException(
                "Cache consistency validation failed."
            );
        }

        if (
            second.statistics.cachedLayers !=
            second.image.getLayers().size()
        ) {
            throw DockerException(
                "Expected all layers to be cached."
            );
        }

        if (
            first.image.imageId() !=
            second.image.imageId()
        ) {
            throw DockerException(
                "Deterministic build validation failed."
            );
        }

        std::cout
            << "All validation checks passed.\n";

        return 0;

    } catch (const std::exception& error) {

        std::cerr
            << "ERROR: "
            << error.what()
            << "\n";

        return 1;
    }
}
