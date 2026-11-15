# Introduction to Containers

## 1. Containerization Fundamentals

Containerization is an application packaging and execution approach in which an application and its required runtime components are distributed as a container image and executed as an isolated container.

A container provides a controlled execution environment without requiring a separate guest operating system for every application instance.

The central distinction is between an image and a container:

| Concept | Meaning |
|---|---|
| Container image | Packaged, versioned application filesystem and execution metadata |
| Image layer | Individual filesystem change or build instruction |
| Container | Runtime instance created from an image |
| Container runtime | Software responsible for creating and managing containers |
| Registry | Storage and distribution service for container images |
| Host | Operating system providing the execution environment |
| Namespace | Kernel mechanism providing isolation of selected resources |
| Cgroup | Linux mechanism for resource accounting and limits |
| Volume | Persistent storage made available to containers |
| Network mapping | Mechanism connecting container network ports to external ports |

A container does not contain an independent guest kernel. Containers running on a Linux host share the host kernel while receiving separate execution environments through operating-system isolation mechanisms.

## 2. Container Architecture

A simplified container architecture is:

Host Operating System
|
+-- Container Runtime
|   |
|   +-- Container A
|   |   +-- Application Process
|   |   +-- Filesystem View
|   |   +-- Network Namespace
|   |   +-- Resource Limits
|   |
|   +-- Container B
|       +-- Application Process
|       +-- Filesystem View
|       +-- Network Namespace
|       +-- Resource Limits
|
+-- Shared Host Kernel
|
+-- Hardware Resources

The runtime manages the lifecycle of containers. The kernel supplies the underlying isolation and resource-management mechanisms.

Containerization reduces the overhead associated with running separate guest operating systems, but it does not eliminate the need for security boundaries.

## 3. Container Images and Application Packaging

A container image packages the filesystem and execution configuration needed to launch an application.

A typical image build follows this sequence:

1. Select a base image.
2. Define the working directory.
3. Copy dependency manifests.
4. Install application dependencies.
5. Copy application source files.
6. Configure the execution user.
7. Define the entrypoint.
8. Build and tag the resulting image.
9. Scan and publish the image.

A representative application image has the following structure:

| Layer | Instruction | Purpose |
|---|---|---|
| 1 | FROM | Select the base filesystem |
| 2 | WORKDIR | Establish the application directory |
| 3 | COPY | Include dependency manifests |
| 4 | RUN | Install application dependencies |
| 5 | COPY | Include application source |

The five implementations represent these layers using structured data.

### Layered filesystem

Image layers represent successive filesystem changes. A later layer adds or modifies filesystem content without requiring the complete image to be reconstructed from the original base.

Layer reuse allows multiple images to share common filesystem components.

This improves distribution efficiency and can reduce storage requirements.

A change to an early layer can invalidate the build cache for subsequent layers. Dependency manifests are therefore commonly copied and processed before frequently changing application source files.

### Image identity

An image reference commonly takes this form:

`repository:tag`

For example:

`inventory-api:1.0.0`

Tags are useful for human-readable version selection. They can be reassigned, so a tag alone does not guarantee immutable identity.

A cryptographic digest provides content-based identification.

The Python, JavaScript and C++ implementations calculate an illustrative SHA-256 digest from layer metadata. The PostgreSQL implementation stores a digest with a uniqueness constraint.

A production image pipeline should verify the actual image manifest and content digest, rather than relying only on descriptive metadata.

## 4. Image Registries

An image registry stores and distributes container images.

The normal distribution workflow is:

Application Source
|
+-- Image Build
|
+-- Image Tagging
|
+-- Image Security Scan
|
+-- Registry Push
|
+-- Registry Pull
|
+-- Runtime Deployment

Registries can be:

- Public registries accessible to external users.
- Private registries controlled by an organization.
- Internal registries used for approved enterprise images.

A trusted registry does not automatically guarantee that every stored image is secure.

Image verification should consider:

- Image digest.
- Base image provenance.
- Dependency versions.
- Vulnerability scan results.
- Software supply-chain integrity.
- Image signatures.
- Execution permissions.

The JavaScript and Java implementations provide registry operations and image validation. The SQL model separates registries, repositories and individual image versions.

## 5. Container Isolation

Container isolation separates selected operating-system resources between applications.

### 5.1 Process isolation

Linux PID namespaces provide separate process identifier views.

A process inside one container generally cannot directly inspect the complete process tree of another isolated container.

The C++ implementation models process limits as part of container resource configuration.

### 5.2 Filesystem isolation

Mount namespaces provide separate mount views.

A container can use its own filesystem view while the host retains control of the underlying storage.

Container image layers are commonly combined using a union or overlay filesystem.

A read-only root filesystem reduces the ability of a compromised application to modify its packaged filesystem.

Writable application data should use deliberately configured writable locations or mounted volumes.

### 5.3 Network isolation

Network namespaces provide separate network stacks.

They can isolate:

- Network interfaces.
- IP addresses.
- Routing tables.
- Network sockets.
- Port spaces.

A container can expose an application port and map it to a host port.

For example:

| Network component | Port |
|---|---:|
| Container application | 8000 |
| Host-accessible endpoint | 8080 |

The Python, JavaScript, C++ and Java implementations validate exposed ports and host mappings.

The JavaScript, C++ and Java implementations also maintain host-port ownership to prevent conflicting allocations.

### 5.4 Resource isolation

Linux control groups provide resource accounting and enforcement.

Important resource categories include:

| Resource | Purpose |
|---|---|
| CPU | Limits or weights for processor usage |
| Memory | Maximum permitted memory consumption |
| Processes | Limits the number of processes |
| I/O | Controls or accounts for storage activity |

The implementations model CPU, memory and process limits.

For example, a container configured with 1.5 CPU cores and 512 MB memory requests those resource allocations from the simulated host.

Resource allocation is not equivalent to actual resource consumption. A CPU limit also does not mean that the application continuously consumes the full allocated amount.

The Python, JavaScript, C++ and Java resource managers reject deployments that exceed available capacity.

## 6. Image Versus Container

| Attribute | Image | Container |
|---|---|---|
| Nature | Packaged artifact | Runtime instance |
| State | Immutable image metadata | Mutable lifecycle state |
| Execution | Not directly executing | Runs application processes |
| Filesystem | Layered image filesystem | Image filesystem plus runtime changes |
| Configuration | Build-time metadata | Runtime configuration |
| Resource allocation | No active allocation | CPU and memory allocation |
| Identity | Repository, tag and digest | Container identifier |
| Persistence | Stored in a registry or local image store | Depends on storage configuration |

One image can produce multiple container instances.

For example:

`inventory-api:1.0.0`

can be used to create:

- Development container.
- Testing container.
- Staging container.
- Production container.

Each instance can have separate environment variables, port mappings and resource allocations.

Changing a running container does not automatically change the original image.

Creating a new image version is the appropriate way to package a deliberate application change.

## 7. Container Lifecycle

The five source implementations use a common lifecycle model.

| State | Description |
|---|---|
| Created | Container instance has been configured |
| Running | Container execution is active |
| Stopped | Container execution has stopped normally |
| Failed | Container execution has terminated unexpectedly |
| Removed | Container instance is no longer available for execution |

The principal lifecycle is:

Created
|
+-- Start
    |
    +-- Running
        |
        +-- Stop
        |   |
        |   +-- Stopped
        |       |
        |       +-- Start
        |
        +-- Failure
            |
            +-- Failed
                |
                +-- Restart Policy
                    |
                    +-- Running

Removal is a separate operation.

A running container must be stopped before removal in the implementations.

A removed container cannot be restarted.

A stopped container can be restarted without rebuilding its original image.

A failed container may be restarted when its configured restart policy permits it.

### Restart policies

| Policy | Behavior |
|---|---|
| No | Do not automatically restart |
| Always | Restart after termination |
| On failure | Restart after unsuccessful termination |

The Python, JavaScript, C++ and Java implementations include restart handling.

The Python, JavaScript and Java implementations demonstrate a bounded restart count for the on-failure policy.

Production systems should also consider restart backoff, maximum retry windows, health checks and repeated failure detection.

## 8. Container Configuration

A container requires runtime configuration beyond its image.

Important configuration elements include:

- Environment variables.
- Port mappings.
- CPU allocation.
- Memory allocation.
- Process limits.
- Restart policy.
- Filesystem permissions.
- Execution user.
- Privileged execution settings.

### Environment variables

Environment variables provide runtime configuration without requiring the application image to be rebuilt.

Examples include:

| Variable | Example value |
|---|---|
| APP_ENV | production |
| LOG_LEVEL | INFO |
| DATABASE_HOST | database.internal |
| PORT | 8000 |

Environment variables are configuration inputs, not a secure secret-storage mechanism.

Passwords, tokens and private keys should be managed through dedicated secret-management facilities.

The PostgreSQL implementation marks sensitive configuration records with `is_secret`, but storing a secret flag does not encrypt the underlying value.

### Port mappings

A container port is not automatically accessible from outside the container.

Port mapping establishes an explicit connection between a host port and a container port.

For example:

`8080:8000`

The host listens on port 8080 and forwards traffic to port 8000 inside the container.

Only ports actually supported by the packaged application should be mapped.

## 9. Health Monitoring

A running container is not necessarily a healthy container.

A container may remain active while its application is unable to process requests.

Health monitoring distinguishes process state from application readiness.

| Health state | Meaning |
|---|---|
| Starting | Initial health verification is in progress |
| Healthy | Health verification succeeded |
| Unhealthy | Health verification failed |

Typical health checks can examine:

- HTTP readiness endpoints.
- Database connectivity.
- Application initialization.
- Internal dependency availability.
- Response time.
- Required background processes.

The Python, JavaScript, C++ and Java programs model health transitions.

The PostgreSQL model records individual health-check results, timestamps and response times.

Production health monitoring should distinguish:

- Liveness: whether the application process is functioning.
- Readiness: whether the application can receive workload.
- Startup: whether application initialization has completed.

Restarting an application because a dependency is temporarily unavailable can sometimes worsen an incident. Health-check behavior must therefore reflect the actual application architecture.

## 10. Resource Scheduling and Admission Control

A host has finite resources.

If multiple containers request resources, the runtime must prevent allocations from exceeding the configured capacity.

For a host:

- Total CPU = 8 cores.
- Total memory = 4096 MB.

Existing containers:

| Container | CPU | Memory |
|---|---:|---:|
| Inventory API | 1.5 | 512 MB |
| Reporting API | 2.0 | 1024 MB |
| Authentication API | 1.0 | 512 MB |

Allocated resources:

- CPU: 4.5 cores.
- Memory: 2048 MB.

Remaining configured capacity:

- CPU: 3.5 cores.
- Memory: 2048 MB.

A new container requesting 4 CPU cores should be rejected by the simulated admission controller.

The implementations use maps or collections to track active allocations.

The PostgreSQL model uses a resource-validation trigger and a node-resource reporting view.

In a production cluster, resource admission must also account for concurrency, reservations, scheduling policies, actual usage, overcommitment and operating-system overhead.

## 11. Security and Container Hardening

Containers provide isolation, but a container should not automatically be considered a complete security boundary.

A secure deployment should apply several controls.

### Image security

- Use approved base images.
- Pin dependencies where appropriate.
- Scan image contents.
- Verify image digests.
- Use trusted image sources.
- Remove unnecessary packages.
- Avoid embedding credentials.
- Rebuild images when vulnerable dependencies are identified.

### Runtime security

- Run applications as non-root users.
- Avoid privileged containers.
- Restrict capabilities.
- Use read-only root filesystems where possible.
- Limit CPU, memory and processes.
- Restrict unnecessary network access.
- Apply appropriate seccomp and mandatory access-control policies.
- Avoid exposing the container runtime socket.

### Supply-chain security

A secure image pipeline should verify the provenance and integrity of the packaged application.

An image digest identifies content, while an image signature can provide evidence about the identity of the signing party and the integrity of the signed artifact.

These mechanisms address different security requirements.

### Security limitations

The source implementations model security policy decisions but do not enforce real Linux capabilities, seccomp profiles, AppArmor, SELinux, kernel isolation or cryptographic image signatures.

Their vulnerability counts are illustrative metadata, not results from an actual vulnerability scanner.

## 12. Python Implementation

The Python file implements a complete object-oriented container simulation.

### Main components

| Component | Responsibility |
|---|---|
| ImageLayer | Represents an image filesystem layer |
| ContainerImage | Stores packaged application metadata |
| ImageRegistry | Publishes and retrieves images |
| ResourceLimits | Defines CPU, memory and process limits |
| ContainerConfig | Validates runtime configuration |
| Container | Manages individual lifecycle transitions |
| ContainerRuntime | Coordinates container operations |

### Important mechanisms

The `dataclass` structures provide explicit domain models.

The `Enum` classes restrict valid state and policy values.

The `ContainerImage.digest` property calculates a SHA-256 digest over layer metadata.

The `ContainerConfig.validate()` method checks ports, environment variables and security restrictions.

The runtime tracks active resource allocations and prevents new deployments from exceeding its simulated host capacity.

The `restart_failed()` method applies restart policies.

The `export_state()` method exports container metadata without exporting environment values.

The script includes assertions that verify image identity, lifecycle behavior and removal restrictions.

### Execution

Run the Python file with Python 3.10 or later.

It requires only the Python standard library.

Execution produces container lifecycle logs and a `container-state.json` operational report.

## 13. JavaScript Implementation

The JavaScript file implements an event-driven container platform using Node.js.

### Main components

| Component | Responsibility |
|---|---|
| ImageLayer | Immutable image-layer metadata |
| ContainerImage | Image identity and configuration |
| ImageRegistry | Image publication and retrieval |
| ResourceScheduler | Host resource allocation |
| PortAllocator | Host-port ownership |
| Container | Lifecycle and event production |
| ContainerPlatform | Deployment coordination |

### Engineering decisions

JavaScript uses private class fields for registry state and event emitters for lifecycle notifications.

The image model uses frozen objects and arrays to reduce accidental mutation.

The `ImageRegistry.pull()` method is asynchronous to represent registry access.

The `ResourceScheduler` maintains active allocations in a `Map`.

The `PortAllocator` prevents multiple active containers from claiming the same host port.

The platform emits lifecycle events when containers start, stop, fail or become healthy.

The audit exporter writes a structured JSON report using the Node.js filesystem API.

### Execution

Run with Node.js 18 or later.

The program requires no npm packages.

Execution generates `container-audit.json`.

## 14. C++17 Implementation

The C++17 file emphasizes explicit domain modeling and resource management.

### Main components

| Component | Responsibility |
|---|---|
| ImageLayer | Layer representation |
| ContainerImage | Packaged image definition |
| ResourceLimits | Resource configuration |
| ContainerConfig | Deployment configuration |
| ResourceManager | Resource admission and release |
| NetworkManager | Port allocation |
| Container | Runtime state management |
| ContainerRuntime | Container creation and inventory |

### Engineering decisions

The image model uses value-based structures and immutable access to packaged metadata.

The resource manager uses associative containers to maintain allocations.

The network manager tracks port ownership through a map.

Container creation uses `std::unique_ptr` to provide automatic memory management.

The runtime validates image vulnerabilities before deployment.

The `Container::start()` method reserves resources and network ports. If network reservation fails, the previously allocated resources are released.

This provides an important transactional behavior within the in-memory simulation.

### Complexity considerations

| Operation | Expected complexity |
|---|---|
| Image metadata lookup | Depends on underlying collection |
| Resource allocation | O(n) |
| Resource release | O(log n) |
| Port ownership lookup | O(log n) |
| Container inventory | O(n) |
| Image layer size calculation | O(n) |

The resource manager uses linear allocation checks because it must calculate active resource usage.

Larger scheduling systems can maintain running allocation totals to reduce repeated aggregation.

### Execution

Compile using a C++17-compatible compiler.

The program uses only the C++ standard library.

## 15. Java 17 Implementation

The Java implementation provides an enterprise-oriented container deployment architecture.

### Main components

| Component | Responsibility |
|---|---|
| ContainerImage | Immutable image definition |
| ImageLayer | Immutable layer metadata |
| ResourceLimits | Validated resource allocation |
| ContainerConfiguration | Immutable runtime configuration |
| SecurityPolicy | Deployment security contract |
| RestrictedSecurityPolicy | Security-policy implementation |
| ResourceManager | Synchronized allocation management |
| NetworkManager | Synchronized port reservation |
| ImageRegistry | Image version management |
| DeploymentService | Deployment orchestration |
| Container | Lifecycle and audit management |

### Enterprise design decisions

Java records represent immutable image layers, resource limits, deployment configuration and audit events.

The `SecurityPolicy` interface separates policy definition from deployment execution.

The restricted implementation rejects:

- Images with known vulnerabilities.
- Root-based images.
- Privileged execution.
- Root execution.
- Writable root filesystems.
- Port mappings not declared by the image.

The `DeploymentService` coordinates registry access, security validation, container creation and startup.

The resource and network managers use synchronized operations to protect shared in-memory state against concurrent modifications.

The audit mechanism records lifecycle transitions with timestamps.

### Execution

Compile and run with Java 17.

The implementation uses no third-party dependencies.

## 16. PostgreSQL Implementation

The PostgreSQL script provides a relational model for container inventory and deployment governance.

### Database entities

| Table | Purpose |
|---|---|
| image_registries | Registry information |
| image_repositories | Repository organization |
| container_images | Versioned image metadata |
| image_layers | Individual image layers |
| image_exposed_ports | Application ports |
| host_nodes | Host resource capacity |
| containers | Container deployment records |
| container_port_mappings | Network mappings |
| container_environment | Runtime configuration metadata |
| container_health_checks | Health monitoring history |
| container_audit_events | Lifecycle audit records |

### Referential integrity

Foreign keys connect repositories to registries, images to repositories and containers to images and host nodes.

Unique constraints prevent duplicate image tags within the same repository and conflicting host-port allocations.

Check constraints validate:

- CPU allocations.
- Memory allocations.
- Process limits.
- Image digests.
- Port ranges.
- Environment variable names.
- Security settings.
- Restart counts.

### Database functions and procedures

`validate_container_resources()` checks requested allocations against host capacity.

`validate_image_deployment()` rejects unscanned, vulnerable and root-based images.

`validate_container_port_mapping()` ensures that mapped ports are declared by the image.

`record_container_state_change()` records lifecycle changes.

`validate_container_transition()` prevents selected invalid state transitions.

`check_deployment_capacity()` evaluates whether a host can accept a requested deployment.

`restart_failed_container()` implements transactional restart handling.

### Reporting

The `container_deployment_eligibility` view identifies images that meet the deployment security requirements.

The `node_resource_usage` view calculates active CPU and memory allocations.

Additional queries report:

- Container inventory.
- Host utilization.
- Image eligibility.
- Health-check performance.
- Lifecycle events.
- Running container capacity.

The SQL script includes sample registries, images, image layers, host nodes and deployments.

The security rejection demonstration intentionally attempts to deploy an image that fails the configured security requirements.

### Database transaction considerations

Resource admission uses a row lock on the selected host node to serialize relevant capacity checks.

This is a simplified single-database scheduling model.

A production scheduler must also coordinate port allocation, deployment state and resource reservation within a consistent transaction boundary.

The database model does not represent actual kernel resource enforcement.

## 17. Containerization Compared with Virtualization

| Characteristic | Containers | Virtual Machines |
|---|---|---|
| Operating system | Share host kernel in conventional Linux container deployments | Each VM runs a guest operating system |
| Startup | Generally faster | Generally slower |
| Resource overhead | Generally lower | Generally higher |
| Isolation mechanism | Namespaces, cgroups and other kernel controls | Hypervisor and virtual hardware |
| Packaging | Container image | VM image |
| Portability | Depends on compatible runtime and host architecture | Depends on hypervisor and hardware compatibility |
| Kernel independence | No independent kernel per conventional container | Independent guest kernel |

Containers and virtual machines are not mutually exclusive.

A container runtime can operate inside a virtual machine, combining VM-level infrastructure isolation with application-level container packaging.

## 18. Portability and Deployment Consistency

Container images improve portability by packaging application dependencies and runtime configuration expectations.

An application packaged into an image can be distributed across compatible environments.

A typical deployment path is:

Development
|
+-- Build Application Image
|
+-- Test Image
|
+-- Scan Image
|
+-- Publish Image
|
+-- Pull by Digest
|
+-- Deploy to Staging
|
+-- Validate Health
|
+-- Deploy to Production

Portability does not mean that every image runs identically on every machine.

Important compatibility factors include:

- CPU architecture.
- Operating-system kernel compatibility.
- Container runtime capabilities.
- Filesystem behavior.
- Network configuration.
- Mounted storage.
- External service availability.
- Environment-specific configuration.

For reproducible deployment, image identity and runtime configuration should be managed separately.

## 19. Failure Scenarios and Edge Cases

| Failure | Expected behavior |
|---|---|
| Image not found | Reject image pull |
| Invalid image metadata | Reject image creation |
| Image digest mismatch | Reject image verification |
| Image fails security scan | Reject deployment |
| Root execution requested | Reject configuration |
| Privileged execution requested | Reject configuration |
| Invalid port | Reject configuration |
| Host port already allocated | Reject startup |
| Insufficient memory | Reject allocation |
| Insufficient CPU | Reject allocation |
| Application health check fails | Mark container unhealthy |
| Application process exits | Mark container failed |
| Restart limit reached | Stop automatic retry attempts |
| Running container removal | Reject removal |
| Removed container restart | Reject restart |

These failure conditions are deliberately represented in the source implementations.

## 20. Limitations of the Implementations

The five source files provide educational models of container concepts rather than production container runtimes.

They do not:

- Create Linux namespaces.
- Configure actual cgroups.
- Mount overlay filesystems.
- Launch isolated operating-system processes.
- Create virtual network interfaces.
- Implement real image-layer extraction.
- Pull OCI images over a network.
- Perform actual vulnerability scanning.
- Verify image signatures.
- Manage persistent volumes.
- Enforce kernel-level security policies.
- Provide distributed scheduling.
- Implement production-grade concurrent orchestration.

The SQL schema records resource allocation and deployment metadata. It does not replace kernel-level enforcement.

The image digest examples are illustrative. A production implementation must calculate and verify digests using the actual image content and manifest specification.

## 21. Technical Concepts Demonstrated

| Concept | Python | JavaScript | C++17 | Java 17 | PostgreSQL |
|---|---|---|---|---|---|
| Image metadata | Yes | Yes | Yes | Yes | Yes |
| Layer modeling | Yes | Yes | Yes | Yes | Yes |
| Registry | Yes | Yes | Basic runtime model | Yes | Yes |
| Container lifecycle | Yes | Yes | Yes | Yes | Yes |
| Resource allocation | Yes | Yes | Yes | Yes | Yes |
| Port management | Validation | Allocation | Allocation | Allocation | Constraints |
| Health monitoring | Yes | Yes | Yes | Yes | Yes |
| Restart policies | Yes | Yes | Yes | Yes | Yes |
| Security validation | Yes | Yes | Yes | Yes | Yes |
| Audit history | Logs | Events | Console | Structured events | Audit table |
| Reporting | JSON | JSON | Console | Collections | Views and queries |

The implementations use different engineering approaches while representing the same central domain: packaged application images, isolated runtime instances, controlled resource allocation, deployment security and operational lifecycle management.
