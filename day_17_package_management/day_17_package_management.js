"use strict";

/*
 * Package Management in JavaScript
 *
 * This standalone Node.js program demonstrates package-management concepts
 * without requiring external npm packages.
 *
 * The implementation models:
 *   - packages and versions
 *   - repositories
 *   - semantic-version constraints
 *   - dependency graphs
 *   - dependency resolution
 *   - npm-style manifests and lock files
 *   - installation and upgrades
 *   - integrity hashes
 *   - development and optional dependencies
 *   - workspace-style projects
 *   - caching
 *   - transactions
 *   - asynchronous package acquisition
 *   - security and operational considerations
 *
 * Run with:
 *   node package-management.js
 */

const crypto = require("crypto");

// ============================================================================
// 1. BASIC OUTPUT
// ============================================================================

function section(title) {
  console.log("\n" + "=".repeat(78));
  console.log(title);
  console.log("=".repeat(78));
}

// ============================================================================
// 2. VERSION MODEL
// ============================================================================

class Version {
  constructor(major, minor, patch) {
    if (![major, minor, patch].every(Number.isInteger) ||
        major < 0 || minor < 0 || patch < 0) {
      throw new Error("Version components must be non-negative integers.");
    }

    this.major = major;
    this.minor = minor;
    this.patch = patch;
  }

  static parse(value) {
    const match = /^(\d+)\.(\d+)\.(\d+)$/.exec(String(value).trim());

    if (!match) {
      throw new Error(`Invalid semantic version: ${value}`);
    }

    return new Version(
      Number(match[1]),
      Number(match[2]),
      Number(match[3])
    );
  }

  compare(other) {
    if (this.major !== other.major) {
      return this.major - other.major;
    }

    if (this.minor !== other.minor) {
      return this.minor - other.minor;
    }

    return this.patch - other.patch;
  }

  toString() {
    return `${this.major}.${this.minor}.${this.patch}`;
  }
}

// ============================================================================
// 3. VERSION CONSTRAINTS
// ============================================================================

class VersionConstraint {
  constructor(expression = "*") {
    this.expression = expression.trim();
  }

  matches(version) {
    const expression = this.expression;

    if (expression === "" || expression === "*") {
      return true;
    }

    if (expression.startsWith("^")) {
      const base = Version.parse(expression.slice(1));

      let upper;

      if (base.major > 0) {
        upper = new Version(base.major + 1, 0, 0);
      } else if (base.minor > 0) {
        upper = new Version(0, base.minor + 1, 0);
      } else {
        upper = new Version(0, 0, base.patch + 1);
      }

      return (
        version.compare(base) >= 0 &&
        version.compare(upper) < 0
      );
    }

    if (expression.startsWith("~")) {
      const base = Version.parse(expression.slice(1));
      const upper = new Version(base.major, base.minor + 1, 0);

      return (
        version.compare(base) >= 0 &&
        version.compare(upper) < 0
      );
    }

    const operators = [">=", "<=", "==", ">", "<"];

    for (const operator of operators) {
      if (expression.startsWith(operator)) {
        const target = Version.parse(expression.slice(operator.length));
        const comparison = version.compare(target);

        switch (operator) {
          case ">=":
            return comparison >= 0;
          case "<=":
            return comparison <= 0;
          case "==":
            return comparison === 0;
          case ">":
            return comparison > 0;
          case "<":
            return comparison < 0;
          default:
            return false;
        }
      }
    }

    return version.compare(Version.parse(expression)) === 0;
  }
}

// ============================================================================
// 4. PACKAGE MODEL
// ============================================================================

class Dependency {
  constructor(name, constraint = "*") {
    this.name = name;
    this.constraint = new VersionConstraint(constraint);
  }
}

class Package {
  constructor({
    name,
    version,
    dependencies = [],
    devDependencies = [],
    optionalDependencies = [],
    sizeKB = 0,
    description = "",
    platform = "any"
  }) {
    this.name = name;
    this.version =
      version instanceof Version ? version : Version.parse(version);

    this.dependencies = dependencies.map((dependency) =>
      dependency instanceof Dependency
        ? dependency
        : new Dependency(dependency.name, dependency.constraint)
    );

    this.devDependencies = devDependencies.map((dependency) =>
      dependency instanceof Dependency
        ? dependency
        : new Dependency(dependency.name, dependency.constraint)
    );

    this.optionalDependencies = optionalDependencies.map((dependency) =>
      dependency instanceof Dependency
        ? dependency
        : new Dependency(dependency.name, dependency.constraint)
    );

    this.sizeKB = sizeKB;
    this.description = description;
    this.platform = platform;

    this.integrity = this.calculateIntegrity();
  }

  artifactContent() {
    const dependencyText = this.dependencies
      .map(
        (dependency) =>
          `${dependency.name}:${dependency.constraint.expression}`
      )
      .join(",");

    return [
      this.name,
      this.version.toString(),
      dependencyText,
      this.platform
    ].join("|");
  }

  calculateIntegrity() {
    return crypto
      .createHash("sha256")
      .update(this.artifactContent())
      .digest("hex");
  }
}

// ============================================================================
// 5. REPOSITORY
// ============================================================================

class Repository {
  constructor(name, { trusted = true } = {}) {
    this.name = name;
    this.trusted = trusted;
    this.packages = new Map();
  }

  publish(packageObject) {
    if (!this.packages.has(packageObject.name)) {
      this.packages.set(packageObject.name, []);
    }

    const versions = this.packages.get(packageObject.name);

    const filtered = versions.filter(
      (existing) =>
        existing.version.compare(packageObject.version) !== 0
    );

    filtered.push(packageObject);

    filtered.sort((a, b) =>
      a.version.compare(b.version)
    );

    this.packages.set(packageObject.name, filtered);
  }

  candidates(name, constraint) {
    const packages = this.packages.get(name) || [];

    return packages.filter((packageObject) =>
      constraint.matches(packageObject.version)
    );
  }

  latestMatching(name, constraint) {
    const candidates = this.candidates(name, constraint);

    if (candidates.length === 0) {
      return null;
    }

    return candidates[candidates.length - 1];
  }

  exact(name, version) {
    const target =
      version instanceof Version ? version : Version.parse(version);

    const packages = this.packages.get(name) || [];

    return (
      packages.find(
        (packageObject) =>
          packageObject.version.compare(target) === 0
      ) || null
    );
  }
}

// ============================================================================
// 6. DEPENDENCY RESOLVER
// ============================================================================

class DependencyResolutionError extends Error {
  constructor(message) {
    super(message);
    this.name = "DependencyResolutionError";
  }
}

class DependencyResolver {
  constructor(repositories) {
    this.repositories = repositories;
  }

  candidates(name, constraint) {
    const result = [];

    for (const repository of this.repositories) {
      if (!repository.trusted) {
        continue;
      }

      result.push(...repository.candidates(name, constraint));
    }

    // Newest compatible version is considered first.
    result.sort((a, b) =>
      b.version.compare(a.version)
    );

    // A package with the same name/version should only be considered once.
    const unique = new Map();

    for (const packageObject of result) {
      const key = `${packageObject.name}@${packageObject.version}`;
      if (!unique.has(key)) {
        unique.set(key, packageObject);
      }
    }

    return [...unique.values()];
  }

  resolve(rootName, rootConstraint) {
    const requirements = [
      {
        name: rootName,
        constraint: new VersionConstraint(rootConstraint),
        requestedBy: "root"
      }
    ];

    return this.search(requirements, new Map());
  }

  search(requirements, selected) {
    if (requirements.length === 0) {
      return selected;
    }

    const [requirement, ...remaining] = requirements;

    if (selected.has(requirement.name)) {
      const selectedPackage = selected.get(requirement.name);

      if (
        requirement.constraint.matches(
          selectedPackage.version
        )
      ) {
        return this.search(remaining, selected);
      }

      throw new DependencyResolutionError(
        `${requirement.requestedBy} requires ` +
        `${requirement.name} ${requirement.constraint.expression}, ` +
        `but ${selectedPackage.version} is selected.`
      );
    }

    const candidates = this.candidates(
      requirement.name,
      requirement.constraint
    );

    if (candidates.length === 0) {
      throw new DependencyResolutionError(
        `No compatible version for ${requirement.name} ` +
        `${requirement.constraint.expression}.`
      );
    }

    for (const candidate of candidates) {
      const nextSelected = new Map(selected);
      nextSelected.set(candidate.name, candidate);

      const nextRequirements = [...remaining];

      for (const dependency of candidate.dependencies) {
        nextRequirements.push({
          name: dependency.name,
          constraint: dependency.constraint,
          requestedBy: candidate.name
        });
      }

      try {
        return this.search(
          nextRequirements,
          nextSelected
        );
      } catch (error) {
        if (!(error instanceof DependencyResolutionError)) {
          throw error;
        }

        // Backtracking allows an older compatible version to be tried when
        // the newest candidate creates a dependency conflict.
      }
    }

    throw new DependencyResolutionError(
      `Unable to resolve ${requirement.name}.`
    );
  }
}

// ============================================================================
// 7. LOCK FILE
// ============================================================================

class LockFile {
  constructor() {
    this.entries = new Map();
  }

  record(packageObject) {
    this.entries.set(packageObject.name, {
      name: packageObject.name,
      version: packageObject.version.toString(),
      integrity: packageObject.integrity
    });
  }

  remove(name) {
    this.entries.delete(name);
  }

  print() {
    for (const entry of [...this.entries.values()].sort(
      (a, b) => a.name.localeCompare(b.name)
    )) {
      console.log(
        `  ${entry.name}@${entry.version} ` +
        `sha256:${entry.integrity.slice(0, 16)}...`
      );
    }
  }
}

// ============================================================================
// 8. PACKAGE CACHE
// ============================================================================

class PackageCache {
  constructor() {
    this.items = new Map();
  }

  key(name, version) {
    return `${name}@${version}`;
  }

  has(name, version) {
    return this.items.has(this.key(name, version));
  }

  put(packageObject) {
    this.items.set(
      this.key(packageObject.name, packageObject.version),
      packageObject
    );
  }

  get(name, version) {
    return this.items.get(this.key(name, version)) || null;
  }
}

// ============================================================================
// 9. ASYNCHRONOUS ARTIFACT ACQUISITION
// ============================================================================

function acquirePackageAsync(packageObject, cache) {
  return new Promise((resolve, reject) => {
    // A real client would download bytes over a network. A short timer models
    // asynchronous I/O without making this program dependent on the network.
    setTimeout(() => {
      try {
        if (packageObject.integrity !== packageObject.calculateIntegrity()) {
          throw new Error(
            `Integrity verification failed for ${packageObject.name}`
          );
        }

        cache.put(packageObject);
        resolve(packageObject);
      } catch (error) {
        reject(error);
      }
    }, 15);
  });
}

// ============================================================================
// 10. PACKAGE MANAGER
// ============================================================================

class PackageManager {
  constructor(repositories) {
    this.repositories = repositories;
    this.installed = new Map();
    this.lockFile = new LockFile();
    this.cache = new PackageCache();
    this.history = [];
  }

  resolver() {
    return new DependencyResolver(this.repositories);
  }

  async install(name, constraint = "*", { includeDev = false } = {}) {
    console.log(`\nInstalling ${name} ${constraint}`);

    const previousState = new Map(this.installed);

    try {
      const resolved = this.resolver().resolve(
        name,
        constraint
      );

      const packages = [...resolved.values()];

      if (includeDev) {
        console.log(
          "Development dependency handling would extend the graph here."
        );
      }

      // Independent artifacts can be acquired concurrently.
      const acquired = await Promise.all(
        packages.map(async (packageObject) => {
          if (
            this.cache.has(
              packageObject.name,
              packageObject.version
            )
          ) {
            return this.cache.get(
              packageObject.name,
              packageObject.version
            );
          }

          return acquirePackageAsync(
            packageObject,
            this.cache
          );
        })
      );

      for (const packageObject of acquired) {
        this.installed.set(
          packageObject.name,
          packageObject
        );

        this.lockFile.record(packageObject);
      }

      this.history.push(
        `install ${name} ${constraint}`
      );

      for (const packageObject of packages.sort(
        (a, b) => a.name.localeCompare(b.name)
      )) {
        console.log(
          `  selected ${packageObject.name}@${packageObject.version}`
        );
      }
    } catch (error) {
      // Restore the package state if acquisition or resolution fails.
      this.installed = previousState;
      throw error;
    }
  }

  remove(name) {
    console.log(`\nRemoving ${name}`);

    if (!this.installed.has(name)) {
      console.log("  package is not installed");
      return;
    }

    const dependents = [];

    for (const packageObject of this.installed.values()) {
      if (packageObject.name === name) {
        continue;
      }

      if (
        packageObject.dependencies.some(
          (dependency) => dependency.name === name
        )
      ) {
        dependents.push(packageObject.name);
      }
    }

    if (dependents.length > 0) {
      throw new Error(
        `${name} is required by ${dependents.join(", ")}`
      );
    }

    this.installed.delete(name);
    this.lockFile.remove(name);
    this.history.push(`remove ${name}`);

    console.log(`  removed ${name}`);
  }

  list() {
    console.log("\nInstalled packages:");

    if (this.installed.size === 0) {
      console.log("  none");
      return;
    }

    for (const packageObject of [...this.installed.values()].sort(
      (a, b) => a.name.localeCompare(b.name)
    )) {
      console.log(
        `  ${packageObject.name}@${packageObject.version}`
      );
    }
  }

  verify() {
    console.log("\nVerifying package integrity:");

    let valid = true;

    for (const packageObject of this.installed.values()) {
      const expected = packageObject.integrity;
      const actual = packageObject.calculateIntegrity();

      if (expected === actual) {
        console.log(
          `  OK   ${packageObject.name}@${packageObject.version}`
        );
      } else {
        console.log(
          `  FAIL ${packageObject.name}@${packageObject.version}`
        );
        valid = false;
      }
    }

    return valid;
  }

  async upgradeAll() {
    console.log("\nChecking available upgrades:");

    const upgrades = [];

    for (const packageObject of this.installed.values()) {
      const candidates = [];

      for (const repository of this.repositories) {
        candidates.push(
          ...repository.candidates(
            packageObject.name,
            new VersionConstraint("*")
          )
        );
      }

      if (candidates.length === 0) {
        continue;
      }

      candidates.sort((a, b) =>
        b.version.compare(a.version)
      );

      const newest = candidates[0];

      if (
        newest.version.compare(packageObject.version) > 0
      ) {
        upgrades.push({
          oldPackage: packageObject,
          newPackage: newest
        });
      }
    }

    if (upgrades.length === 0) {
      console.log("  no upgrades available");
      return;
    }

    for (const upgrade of upgrades) {
      console.log(
        `  ${upgrade.oldPackage.name}: ` +
        `${upgrade.oldPackage.version} -> ` +
        `${upgrade.newPackage.version}`
      );

      await acquirePackageAsync(
        upgrade.newPackage,
        this.cache
      );

      this.installed.set(
        upgrade.newPackage.name,
        upgrade.newPackage
      );

      this.lockFile.record(
        upgrade.newPackage
      );
    }

    this.history.push("upgrade-all");
  }

  printHistory() {
    console.log("\nTransaction history:");

    this.history.forEach((entry, index) => {
      console.log(
        `  ${(index + 1).toString().padStart(2, "0")}. ${entry}`
      );
    });
  }
}

// ============================================================================
// 11. NPM-STYLE MANIFEST
// ============================================================================

function createManifest() {
  return {
    name: "analytics-dashboard",
    version: "1.0.0",
    private: true,
    scripts: {
      test: "node test.js",
      build: "node build.js"
    },
    dependencies: {
      "http-core": "^1.0.0",
      "parser": "^1.0.0"
    },
    devDependencies: {
      "test-runner": "^2.0.0"
    },
    optionalDependencies: {
      "native-accelerator": "^1.0.0"
    }
  };
}

function explainManifest(manifest) {
  section("Package manifest structure");

  console.log("Project:", manifest.name);
  console.log("Version:", manifest.version);
  console.log("Private project:", manifest.private);

  console.log("\nRuntime dependencies:");
  for (const [name, constraint] of Object.entries(
    manifest.dependencies
  )) {
    console.log(`  ${name}: ${constraint}`);
  }

  console.log("\nDevelopment dependencies:");
  for (const [name, constraint] of Object.entries(
    manifest.devDependencies
  )) {
    console.log(`  ${name}: ${constraint}`);
  }

  console.log("\nOptional dependencies:");
  for (const [name, constraint] of Object.entries(
    manifest.optionalDependencies
  )) {
    console.log(`  ${name}: ${constraint}`);
  }

  console.log(
    "\nThe manifest declares intent; a lock file records concrete resolution."
  );
}

// ============================================================================
// 12. DEPENDENCY GRAPH
// ============================================================================

function createDependencyGraph(packages) {
  const graph = new Map();

  for (const packageObject of packages) {
    graph.set(
      packageObject.name,
      new Set(
        packageObject.dependencies.map(
          (dependency) => dependency.name
        )
      )
    );
  }

  return graph;
}

function hasCycle(graph) {
  const visiting = new Set();
  const visited = new Set();

  function visit(node) {
    if (visiting.has(node)) {
      return true;
    }

    if (visited.has(node)) {
      return false;
    }

    visiting.add(node);

    for (const dependency of graph.get(node) || []) {
      if (visit(dependency)) {
        return true;
      }
    }

    visiting.delete(node);
    visited.add(node);

    return false;
  }

  for (const node of graph.keys()) {
    if (visit(node)) {
      return true;
    }
  }

  return false;
}

// ============================================================================
// 13. WORKSPACES
// ============================================================================

class Workspace {
  constructor(name) {
    this.name = name;
    this.projects = new Map();
  }

  addProject(projectName, manifest) {
    this.projects.set(projectName, manifest);
  }

  print() {
    console.log(`Workspace: ${this.name}`);

    for (const [projectName, manifest] of this.projects) {
      console.log(
        `  ${projectName}@${manifest.version}`
      );
    }
  }
}

function demonstrateWorkspace() {
  section("Workspace-style multi-package projects");

  const workspace = new Workspace("company-platform");

  workspace.addProject(
    "web-app",
    {
      name: "web-app",
      version: "1.0.0",
      dependencies: {
        "http-core": "^1.0.0"
      }
    }
  );

  workspace.addProject(
    "api-service",
    {
      name: "api-service",
      version: "1.0.0",
      dependencies: {
        "database-driver": "^3.0.0"
      }
    }
  );

  workspace.print();

  console.log(
    "\nWorkspaces allow related packages to be managed as one repository."
  );
}

// ============================================================================
// 14. CONFLICT DEMONSTRATION
// ============================================================================

function demonstrateConflict() {
  section("Dependency conflict");

  const repository = new Repository("conflict-repository");

  repository.publish(
    new Package({
      name: "core",
      version: "1.5.0"
    })
  );

  repository.publish(
    new Package({
      name: "core",
      version: "2.0.0"
    })
  );

  repository.publish(
    new Package({
      name: "legacy-tool",
      version: "1.0.0",
      dependencies: [
        new Dependency("core", "<2.0.0")
      ]
    })
  );

  repository.publish(
    new Package({
      name: "modern-tool",
      version: "1.0.0",
      dependencies: [
        new Dependency("core", ">=2.0.0")
      ]
    })
  );

  repository.publish(
    new Package({
      name: "conflicting-app",
      version: "1.0.0",
      dependencies: [
        new Dependency("legacy-tool", "==1.0.0"),
        new Dependency("modern-tool", "==1.0.0")
      ]
    })
  );

  try {
    new DependencyResolver([repository]).resolve(
      "conflicting-app",
      "==1.0.0"
    );
  } catch (error) {
    console.log("Expected failure:");
    console.log(`  ${error.message}`);
  }
}

// ============================================================================
// 15. SECURITY MODEL
// ============================================================================

function demonstrateSecurity() {
  section("Package-management security");

  const controls = [
    "Use trusted repositories.",
    "Verify cryptographic integrity.",
    "Use lock files for reproducible production builds.",
    "Audit direct and transitive dependencies.",
    "Protect registry tokens and credentials.",
    "Minimize unnecessary dependencies.",
    "Review lifecycle or installation scripts.",
    "Keep the package manager itself updated.",
    "Separate development and production dependencies.",
    "Treat suspicious package behavior as a supply-chain risk."
  ];

  for (const control of controls) {
    console.log(`- ${control}`);
  }
}

// ============================================================================
// 16. BUILD SAMPLE REPOSITORY
// ============================================================================

function buildRepository() {
  const repository = new Repository(
    "central-registry",
    { trusted: true }
  );

  repository.publish(
    new Package({
      name: "http-core",
      version: "1.0.0",
      sizeKB: 180,
      description: "HTTP primitives"
    })
  );

  repository.publish(
    new Package({
      name: "http-core",
      version: "1.1.0",
      sizeKB: 220,
      description: "HTTP primitives with pooling"
    })
  );

  repository.publish(
    new Package({
      name: "http-core",
      version: "2.0.0",
      sizeKB: 300,
      description: "Redesigned HTTP API"
    })
  );

  repository.publish(
    new Package({
      name: "parser",
      version: "1.0.0",
      dependencies: [
        new Dependency("http-core", "^1.0.0")
      ],
      sizeKB: 90
    })
  );

  repository.publish(
    new Package({
      name: "parser",
      version: "1.1.0",
      dependencies: [
        new Dependency("http-core", "^1.0.0")
      ],
      sizeKB: 110
    })
  );

  repository.publish(
    new Package({
      name: "database-driver",
      version: "3.0.0",
      dependencies: [
        new Dependency("http-core", ">=1.1.0")
      ],
      sizeKB: 750
    })
  );

  repository.publish(
    new Package({
      name: "analytics-app",
      version: "1.0.0",
      dependencies: [
        new Dependency("parser", "^1.0.0"),
        new Dependency("database-driver", "==3.0.0")
      ],
      sizeKB: 1200
    })
  );

  repository.publish(
    new Package({
      name: "analytics-app",
      version: "1.1.0",
      dependencies: [
        new Dependency("parser", "^1.1.0"),
        new Dependency("database-driver", "==3.0.0")
      ],
      sizeKB: 1300
    })
  );

  return repository;
}

// ============================================================================
// 17. MAIN PROGRAM
// ============================================================================

async function main() {
  section("PACKAGE MANAGEMENT IN JAVASCRIPT");

  console.log(
    "Package management connects package metadata, repositories, " +
    "dependency resolution, artifact acquisition, verification, and " +
    "environment state."
  );

  section("Version comparison");

  const versions = [
    Version.parse("1.0.0"),
    Version.parse("1.2.0"),
    Version.parse("1.2.5"),
    Version.parse("2.0.0")
  ];

  for (const version of versions) {
    console.log(version.toString());
  }

  console.log(
    "1.2.5 > 1.2.0:",
    Version.parse("1.2.5").compare(
      Version.parse("1.2.0")
    ) > 0
  );

  section("Constraint matching");

  for (const expression of [
    "^1.2.0",
    "~1.2.0",
    ">=1.2.0",
    "<2.0.0",
    "==1.2.5"
  ]) {
    const accepted = versions
      .filter((version) =>
        new VersionConstraint(expression).matches(version)
      )
      .map((version) => version.toString());

    console.log(`${expression.padEnd(10)} -> ${accepted.join(", ")}`);
  }

  const repository = buildRepository();

  section("Repository packages");

  for (const [name, packages] of repository.packages) {
    console.log(
      `${name}: ${packages.map(
        (packageObject) => packageObject.version.toString()
      ).join(", ")}`
    );
  }

  section("Dependency resolution");

  const resolved = new DependencyResolver(
    [repository]
  ).resolve(
    "analytics-app",
    "==1.0.0"
  );

  for (const packageObject of [...resolved.values()].sort(
    (a, b) => a.name.localeCompare(b.name)
  )) {
    console.log(
      `  ${packageObject.name}@${packageObject.version}`
    );
  }

  const graph = createDependencyGraph(
    resolved.values()
  );

  console.log(
    "Dependency cycle detected:",
    hasCycle(graph)
  );

  const manager = new PackageManager(
    [repository]
  );

  try {
    await manager.install(
      "analytics-app",
      "==1.0.0"
    );
  } catch (error) {
    console.error(
      "Installation failed:",
      error.message
    );
  }

  manager.list();
  manager.verify();

  section("Lock file");

  manager.lockFile.print();

  await manager.upgradeAll();

  manager.list();

  section("Cache");

  const cachedPackage = manager.cache.get(
    "http-core",
    Version.parse("1.1.0")
  );

  console.log(
    "http-core@1.1.0 cached:",
    cachedPackage !== null
  );

  const manifest = createManifest();
  explainManifest(manifest);

  demonstrateWorkspace();
  demonstrateConflict();
  demonstrateSecurity();

  section("Important operational distinctions");

  console.log(
    "Manifest: declares dependency intent."
  );

  console.log(
    "Lock file: records an exact resolved dependency graph."
  );

  console.log(
    "Repository: publishes metadata and artifacts."
  );

  console.log(
    "Cache: stores artifacts locally to reduce repeated acquisition."
  );

  console.log(
    "Installed state: represents what is actually present in an environment."
  );

  section("Common package-management commands conceptually");

  const commands = {
    install: "Resolve and install requested software.",
    update: "Refresh repository metadata.",
    upgrade: "Install newer available versions.",
    remove: "Uninstall software when dependency rules permit.",
    list: "Display installed packages.",
    search: "Find packages in repository metadata.",
    audit: "Inspect dependencies for known security problems.",
    verify: "Check installed artifact integrity.",
    clean: "Remove unnecessary cached data."
  };

  for (const [command, meaning] of Object.entries(commands)) {
    console.log(
      `${command.padEnd(10)} ${meaning}`
    );
  }

  section("Edge cases");

  try {
    Version.parse("not-a-version");
  } catch (error) {
    console.log(
      "Malformed version handled:",
      error.message
    );
  }

  try {
    await manager.install(
      "does-not-exist",
      "==1.0.0"
    );
  } catch (error) {
    console.log(
      "Missing package handled:",
      error.message
    );
  }

  manager.printHistory();

  section("Program complete");

  console.log(
    "The implementation demonstrates how package managers coordinate " +
    "declarations, constraints, repositories, resolution, asynchronous " +
    "artifact acquisition, integrity checks, installed state, caching, " +
    "and reproducibility."
  );
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exitCode = 1;
});
