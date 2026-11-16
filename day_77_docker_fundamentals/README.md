# Docker Fundamentals: Architecture, Images, Containers and Registries

## 1. Technical Scope

Docker is a containerization platform that packages applications and their dependencies into portable units called containers.

A container provides an isolated execution environment while sharing the host operating system kernel. This differs from a traditional virtual machine, which generally runs a separate guest operating system.

This project implements a Docker learning environment across five technical perspectives:

- Python: Docker architecture and container lifecycle simulation.
- JavaScript: Event-driven container operations and resource policy evaluation.
- C++17: Container engine and resource governance.
- Java 17: Enterprise container deployment and domain modeling.
- PostgreSQL: Relational storage, operational validation and deployment reporting.

The implementations model Docker management concepts. The Python and JavaScript programs also provide optional integration with an installed Docker CLI. The C++, Java and SQL programs implement management simulations rather than directly controlling a Docker daemon.

## 2. Docker Architecture

Docker uses a client-server architecture.

The principal components are:

| Component | Responsibility |
|---|---|
| Docker CLI | Receives user commands |
| Docker API | Provides the communication interface |
| Docker daemon (`dockerd`) | Manages Docker resources |
| containerd | Manages container lifecycle operations |
| runc | Creates and starts isolated container processes |
| BuildKit | Builds container images |
| Registry | Stores and distributes images |

### Architecture and command flow

    User
      |
      v
    Docker CLI
      |
      v
    Docker API
      |
      v
    Docker daemon (dockerd)
      |
      +--------------------+
      |                    |
      v                    v
    BuildKit             containerd
      |                    |
      v                    v
    Image layers           runc
                           |
                           v
                       Container

    Docker daemon
      |
      v
    Registry
      |
      v
    Image distribution

The Docker CLI communicates with the daemon through the Docker API. The daemon manages Docker resources and delegates container lifecycle operations to lower-level components.

A registry is an image distribution service. It is not the component responsible for executing containers.

### Linux isolation mechanisms

Linux containers rely on operating-system facilities.

| Mechanism | Purpose |
|---|---|
| Namespaces | Isolate process, network, mount and other resource views |
| cgroups | Control and account for resource consumption |
| Union or layered filesystems | Combine image layers |
| Capabilities | Restrict privileged operating-system operations |
| seccomp | Restrict available system calls |
| Linux security modules | Apply additional access controls |

These mechanisms provide process isolation and resource control without requiring a separate guest operating system for every container.

## 3. Docker Images

A Docker image is an immutable, layered template used to create containers.

An image normally contains:

- Base filesystem content.
- Application dependencies.
- Application files.
- Runtime configuration.
- Metadata.
- Entrypoint and command definitions.

### Image references

A typical image reference is:

`nginx:1.27`

Its components are:

| Component | Meaning |
|---|---|
| `nginx` | Repository |
| `1.27` | Tag |

A registry-qualified reference can be:

`registry.example.com/training/web-api:1.0.0`

A digest-qualified reference identifies image content by a cryptographic digest:

`registry.example.com/training/web-api@sha256:<64-hex-character-digest>`

Tags are mutable references. A tag can point to a different image after it is updated. Digests provide content-addressable identification and are preferable when reproducible image selection is required.

### Image layers

Images are constructed from layers.

An illustrative Dockerfile is:

    FROM python:3.13-slim
    WORKDIR /app
    COPY requirements.txt .
    RUN pip install --no-cache-dir -r requirements.txt
    COPY . .
    CMD ["python", "app.py"]

The resulting image contains filesystem changes associated with its build instructions.

A simplified image structure is:

    Image: web-api:1.0.0
      |
      +-- Application layer
      |
      +-- Dependency layer
      |
      +-- Base image layers

Image layers can be shared between different images when their content is identical.

This reduces storage requirements and avoids unnecessary transfer of existing layers.

### Layer caching

Docker uses build caching to avoid repeating unchanged build operations.

For example, copying the dependency manifest before copying frequently modified application files can improve build-cache reuse.

A change in an earlier build instruction may invalidate subsequent cached instructions.

The Python, JavaScript, C++ and Java implementations represent layers through structured records containing identifiers, instructions and sizes.

The PostgreSQL implementation stores layer order, digest, instruction and size in a separate relational table.

### Image and container distinction

| Image | Container |
|---|---|
| Immutable template | Runtime instance |
| Contains filesystem layers | Uses image layers plus a writable layer |
| Can have multiple tags | Has its own identifier |
| Can be distributed through registries | Executes processes |
| Can create multiple containers | Has an independent lifecycle |

An image does not become a container when executed. Docker creates a container from the image and maintains the container's runtime state separately.

## 4. Docker Containers

A container is an isolated execution instance created from an image.

Multiple containers can use the same image while maintaining independent runtime configurations.

### Container lifecycle

The implementations model these states:

| State | Meaning |
|---|---|
| Created | Container exists but has not started |
| Running | Container process is executing |
| Paused | Container processes are suspended |
| Restarting | Container is undergoing restart |
| Exited | Container process has stopped |
| Dead | Container is no longer operational |

The educational lifecycle model uses these transitions:

    Created
       |
       v
    Running <------+
       |           |
       v           |
    Paused --------+
       |
       v
    Exited
       |
       v
    Running

A dead container cannot be restarted.

Docker's actual lifecycle includes additional details, including process exit codes, health checks, restart policies and runtime-specific failure conditions.

### Container creation and execution

The normal operational sequence is:

1. Obtain an image.
2. Create a container from the image.
3. Configure environment variables.
4. Configure port mappings.
5. Attach storage volumes.
6. Apply CPU and memory constraints.
7. Start the container.
8. Inspect its state and logs.
9. Stop, restart or remove it when necessary.

### Container writable layer

An image provides read-only filesystem layers.

A container adds a writable layer for runtime filesystem changes.

Changes written only to this layer are associated with the container and are not automatically incorporated into the original image.

Persistent application data should normally be stored in Docker volumes or appropriate bind mounts.

### Resource management

Containers can be configured with resource limits.

| Resource | Configuration purpose |
|---|---|
| CPU | Limits CPU allocation |
| Memory | Restricts memory consumption |
| PIDs | Limits process creation |
| Storage | Controls or monitors storage consumption |
| Network | Controls communication |
| Ports | Defines host-to-container access |

The implementations use CPU and memory limits as explicit deployment-policy inputs.

A container's resource configuration is not equivalent to its actual resource consumption.

## 5. Docker Registries

A registry stores and distributes container images.

Registries support image publishing, retrieval and distribution between development and deployment environments.

Examples of registry services include:

- Docker Hub.
- Private organizational registries.
- Cloud-hosted container registries.

### Registry workflow

    Developer
       |
       v
    Build image
       |
       v
    Tag image
       |
       v
    Authenticate
       |
       v
    Push image
       |
       v
    Registry
       |
       v
    Pull image
       |
       v
    Deployment environment
       |
       v
    Create container

### Important registry operations

| Operation | Purpose |
|---|---|
| Login | Authenticate with registry |
| Pull | Download an image |
| Tag | Assign an image reference |
| Push | Upload an image |
| Inspect | Examine image metadata |
| Logout | End an authentication session |

Typical commands:

| Command | Function |
|---|---|
| `docker login` | Authenticate |
| `docker logout` | End registry authentication |
| `docker pull nginx:1.27` | Download an image |
| `docker images` | List local images |
| `docker tag` | Create another image reference |
| `docker push` | Upload an image |
| `docker image inspect` | Inspect image metadata |
| `docker image rm` | Remove an image reference |

### Registry security

Registry security requires:

- TLS-protected communication.
- Appropriate authentication.
- Repository-level authorization.
- Restricted push permissions.
- Image provenance verification.
- Digest-based image selection.
- Credential protection.

Authentication establishes identity. Authorization determines whether an identity can perform operations such as pulling or pushing images.

The JavaScript, C++ and Java registry implementations distinguish authenticated users from image distribution operations.

The PostgreSQL schema represents registry membership and push/pull events without storing authentication tokens.

## 6. Docker Networking and Port Mapping

Containers can communicate through Docker-managed networks.

Docker supports several network drivers.

| Network type | Characteristics |
|---|---|
| Bridge | Common networking option for containers on one Docker host |
| Host | Uses the host network namespace |
| None | Disables normal container networking |
| Overlay | Supports communication across participating Docker hosts |
| Macvlan | Provides network interfaces with distinct MAC addresses |

### Port mapping

A container service can listen on an internal port while Docker exposes a host port.

Example:

`docker run -d --name web -p 8080:80 nginx:1.27`

The mapping is:

| Host | Container |
|---|---|
| 8080 | 80 |

A client accesses the application through the host's exposed port.

Port publication is distinct from container networking. A container can communicate through a Docker network without necessarily publishing its ports externally.

The implementations validate port numbers and maintain host-to-container mappings.

Port conflicts must be considered when deploying multiple containers on the same host.

## 7. Docker Volumes and Persistent Storage

Containers have writable filesystem layers, but these layers are not an appropriate default location for important persistent application data.

Docker provides persistent storage mechanisms.

| Storage mechanism | Description |
|---|---|
| Named volume | Docker-managed persistent storage |
| Bind mount | Maps a host filesystem path into a container |
| tmpfs mount | Uses memory-backed temporary storage |

Example:

`docker volume create application-data`

A volume can be mounted when starting a container:

`docker run -d --name database -v application-data:/var/lib/data nginx:1.27`

The example uses an Nginx image only to demonstrate mount syntax. A real database deployment must use the appropriate database image and data directory.

Bind mounts can provide access to host files but require careful permission management.

Read-only mounts are useful when containers should consume configuration without modifying the host files.

The implementations represent volume mappings through host and container paths and include read-only configuration in the database model.

## 8. Docker Fundamentals: Practical Commands

The following commands represent common Docker operations.

### Installation and environment inspection

| Command | Purpose |
|---|---|
| `docker --version` | Display Docker CLI version |
| `docker version` | Display client and server information |
| `docker info` | Inspect Docker daemon configuration |
| `docker context ls` | List Docker contexts |
| `docker context show` | Display the active context |

Docker Desktop provides a graphical environment for Docker on supported desktop operating systems.

On Linux, Docker Engine can be installed and managed as a system service.

### Image operations

| Command | Purpose |
|---|---|
| `docker pull nginx:1.27` | Pull an image |
| `docker images` | List local images |
| `docker image ls` | Alternative image listing |
| `docker image inspect nginx:1.27` | Inspect an image |
| `docker image history nginx:1.27` | Display image build history |
| `docker image rm nginx:1.27` | Remove an image |

### Container operations

| Command | Purpose |
|---|---|
| `docker create nginx:1.27` | Create a container |
| `docker run nginx:1.27` | Create and start a container |
| `docker run -d nginx:1.27` | Start in detached mode |
| `docker ps` | List running containers |
| `docker ps -a` | List all containers |
| `docker start CONTAINER` | Start an existing container |
| `docker stop CONTAINER` | Stop a container |
| `docker restart CONTAINER` | Restart a container |
| `docker pause CONTAINER` | Pause container processes |
| `docker unpause CONTAINER` | Resume container processes |
| `docker rm CONTAINER` | Remove a container |
| `docker inspect CONTAINER` | Inspect container configuration |
| `docker logs CONTAINER` | Read container logs |
| `docker exec -it CONTAINER sh` | Open a shell inside a running container |

### Building images

The command:

`docker build -t training/web-api:1.0.0 .`

Builds an image using the Dockerfile and build context in the current directory.

The build context is the collection of files made available to the build process.

A `.dockerignore` file excludes unnecessary files from the build context.

This can reduce transfer overhead and prevent accidental inclusion of sensitive files.

### Cleanup operations

| Command | Purpose |
|---|---|
| `docker container prune` | Remove stopped containers |
| `docker image prune` | Remove eligible dangling images |
| `docker volume ls` | List volumes |
| `docker volume prune` | Remove eligible unused volumes |
| `docker system df` | Inspect Docker disk usage |
| `docker system prune` | Remove selected unused Docker resources |

Cleanup commands should be reviewed before execution. Removing volumes or images can affect workloads and data availability.

## 9. Python Implementation

The Python implementation provides a domain-oriented Docker simulator.

### Main components

| Component | Responsibility |
|---|---|
| `DockerArchitecture` | Describes architectural components |
| `ImageLayer` | Represents a filesystem layer |
| `DockerImage` | Models an image manifest |
| `ImageStore` | Maintains local images |
| `Registry` | Models authentication and distribution |
| `Container` | Implements lifecycle transitions |
| `DockerEngine` | Coordinates image and container operations |
| `DockerCLI` | Invokes actual Docker CLI commands |
| `InventoryStorage` | Persists management information |

### Implementation decisions

Dataclasses provide structured domain objects. Enums constrain lifecycle and image-origin values.

Dictionaries provide efficient lookups for image references and container identifiers.

Sets maintain unique container names and authenticated registry identities.

The lifecycle model rejects invalid operations instead of silently modifying container state.

The Docker CLI wrapper uses `subprocess.run` with argument lists rather than shell command construction. This reduces command-injection exposure.

The inventory mechanism uses JSON for portability and straightforward inspection.

### Execution

Run the demonstration:

`python docker_fundamentals.py --demo`

Run tests:

`python docker_fundamentals.py --test`

Inspect an installed Docker environment:

`python docker_fundamentals.py --real`

Run all simulator tests and the demonstration:

`python docker_fundamentals.py --demo --test`

The real Docker inspection requires an installed CLI and an accessible Docker daemon.

## 10. JavaScript Implementation

The JavaScript implementation emphasizes asynchronous behavior and event-driven state management.

### Main components

| Component | Responsibility |
|---|---|
| `ImageLayer` | Represents a content layer |
| `DockerImage` | Creates an image manifest |
| `ImageStore` | Maintains local image references |
| `ImageRegistry` | Simulates image distribution |
| `ResourcePolicy` | Evaluates resource allocations |
| `DockerContainer` | Manages container state |
| `DockerEngine` | Coordinates container operations |
| `InventoryRepository` | Persists inventory data |

### Event-driven behavior

The container extends Node.js `EventEmitter`.

Lifecycle operations emit `stateChanged` events.

The engine subscribes to these events and forwards them to external listeners.

This separates the state-changing operation from its consumers.

A monitoring service, event logger or reporting component can subscribe without changing the container implementation.

### Asynchronous operations

Registry pulls and container restarts demonstrate asynchronous execution.

Inventory persistence uses Node.js filesystem promises.

The Docker CLI wrapper uses `spawn` with `shell: false`, argument validation and execution timeouts.

This avoids unnecessary shell interpretation and reduces command-injection risk.

### Execution

Run the demonstration:

`node docker_fundamentals.js demo`

Run tests:

`node docker_fundamentals.js test`

Inspect an installed Docker environment:

`node docker_fundamentals.js real`

The real environment inspection requires Docker CLI access and a running daemon.

## 11. C++17 Implementation

The C++ implementation focuses on explicit ownership, domain modeling and resource governance.

### Main components

| Component | Responsibility |
|---|---|
| `DockerArchitecture` | Represents Docker architecture |
| `ImageLayer` | Models image layers |
| `DockerImage` | Stores image metadata |
| `ImageStore` | Maintains local image references |
| `ImageRegistry` | Models remote image distribution |
| `ResourcePolicy` | Enforces allocation limits |
| `DockerContainer` | Implements lifecycle transitions |
| `DockerEngine` | Coordinates container deployment |

### Implementation decisions

`std::vector` maintains ordered image layers.

`std::unordered_map` provides efficient image lookups.

`std::map` maintains ordered container inventories and configuration mappings.

`std::set` enforces uniqueness.

`std::shared_ptr<const DockerImage>` allows multiple containers to reference the same immutable image.

`std::unique_ptr<DockerContainer>` provides clear ownership of container objects within the engine.

Exceptions represent invalid configuration, missing resources and prohibited state transitions.

### Complexity considerations

| Operation | Expected complexity |
|---|---|
| Image lookup | O(1) average |
| Image insertion | O(1) average |
| Ordered container lookup | O(log n) |
| Layer aggregation | O(L) |
| Resource validation | O(P) |
| Container inventory traversal | O(C) |

Where:

- `n` represents stored images.
- `L` represents image layers.
- `P` represents port mappings.
- `C` represents containers.

### Compilation

Compile:

`g++ -std=c++17 -O2 -Wall -Wextra -pedantic docker_fundamentals.cpp -o docker_lab`

Run:

`./docker_lab demo`

Run automated tests:

`./docker_lab test`

On Windows:

`docker_lab.exe demo`

`docker_lab.exe test`

## 12. Java 17 Implementation

The Java implementation models an enterprise-oriented container deployment service.

### Main components

| Component | Responsibility |
|---|---|
| `ArchitectureService` | Describes Docker architecture |
| `ImageLayer` | Immutable image-layer record |
| `ImageManifest` | Immutable image representation |
| `ImageRepository` | Image storage service |
| `RegistryService` | Registry authentication and distribution |
| `ContainerConfiguration` | Validated deployment configuration |
| `DeploymentPolicy` | Policy evaluation interface |
| `EnterpriseResourcePolicy` | Resource restrictions |
| `ContainerEntity` | Container lifecycle and audit history |
| `ContainerDeploymentService` | Deployment orchestration |

### Enterprise design decisions

Java records represent immutable image layers, manifests and container configuration.

Interfaces separate policy evaluation from deployment orchestration.

Custom exceptions distinguish resource-policy failures, authentication failures and invalid lifecycle transitions.

The deployment service validates a container configuration before creating a container.

The container maintains its own audit trail of state transitions.

Synchronized methods protect individual in-memory state-changing operations against concurrent access.

The implementation uses immutable collections for externally exposed configuration and audit data.

The application uses no third-party dependencies.

### Compilation

Compile:

`javac DockerFundamentals.java`

Run:

`java DockerFundamentals`

Run tests with assertions enabled:

`java -ea DockerFundamentals test`

The Java tests use assertions and therefore require the `-ea` option.

## 13. PostgreSQL Implementation

The PostgreSQL implementation models Docker inventory and deployment management as a relational system.

### Database entities

| Table | Purpose |
|---|---|
| `docker_users` | User identities and roles |
| `registries` | Registry information |
| `registry_memberships` | Registry access permissions |
| `image_repositories` | Repository metadata |
| `images` | Image manifests |
| `image_layers` | Individual image layers |
| `image_distribution_events` | Image push and pull operations |
| `resource_policies` | Deployment resource limits |
| `containers` | Container inventory |
| `container_ports` | Port mappings |
| `container_volumes` | Persistent storage configuration |
| `container_environment` | Container environment configuration |
| `container_audit` | Lifecycle and operational audit history |

### Relational model

    Docker Users
       |
       +------ Registry Memberships
       |                |
       |                v
       |             Registries
       |                |
       |                v
       |         Image Repositories
       |                |
       |                v
       |              Images
       |                |
       |                v
       |           Image Layers
       |
       +------ Containers
                    |
                    +------ Container Ports
                    |
                    +------ Container Volumes
                    |
                    +------ Environment Variables
                    |
                    +------ Resource Policies
                    |
                    +------ Container Audit

### Integrity mechanisms

The database uses:

- Primary keys for entity identity.
- Foreign keys for relational integrity.
- Unique constraints for repository and image references.
- Check constraints for ports, resource allocations and identifiers.
- Enumerated types for controlled states.
- Triggers for lifecycle validation and audit recording.
- Functions for deployment eligibility.
- Procedures for deployment processing.
- Views for inventory reporting.
- Indexes for frequent operational queries.

### Deployment eligibility

The `evaluate_container_eligibility` function checks:

1. Whether the container exists.
2. Whether its resource policy is active.
3. Whether CPU allocation is within the configured maximum.
4. Whether memory allocation is within the configured maximum.
5. Whether the port allocation is permitted.
6. Whether privileged execution is permitted.
7. Whether host networking is permitted.

The procedure `process_container_deployment` records the eligibility result.

The database does not claim that a deployment is operational merely because its configuration is eligible. Actual deployment requires successful execution by a Docker daemon.

### Transaction management

The SQL demonstrates transactional state changes.

A pause or resume operation is performed inside a transaction.

If a database operation fails, PostgreSQL can roll back the transaction rather than preserve an incomplete state change.

### Performance considerations

The schema indexes frequently queried fields, including:

- Image repository identifiers.
- Image-layer ordering.
- Container lifecycle states.
- Deployment status.
- Container ownership.
- Audit timestamps.

The reporting views simplify common inventory queries.

Large installations would also benefit from pagination, retention policies, partitioning of high-volume audit data and careful review of query plans.

## 14. Important Technical Distinctions

### Docker image versus Docker container

An image defines the filesystem and metadata used to create a container.

A container is a runtime instance with an independent lifecycle and writable layer.

### Docker daemon versus containerd

The Docker daemon manages Docker resources and API-level operations.

containerd provides container lifecycle management and delegates low-level container creation to a runtime such as runc.

### Registry versus image repository

A registry hosts and distributes repositories.

A repository organizes related images and their tags.

A registry can host many repositories.

### Tag versus digest

A tag is a human-readable image reference that can be reassigned.

A digest identifies content by its cryptographic hash.

A digest is preferable when exact image identity matters.

### Volume versus writable layer

The writable layer belongs to the container.

A volume provides storage that can persist independently of a container's lifecycle.

### Docker command versus Docker API

The Docker CLI provides a convenient interface to the Docker API.

Applications can also interact with the API through supported client libraries or direct API communication.

### Container isolation versus virtual machines

Containers share the host operating system kernel.

Virtual machines normally run separate guest operating systems under a hypervisor.

This affects resource overhead, isolation boundaries and operational architecture.

## 15. Security Considerations

Containerization does not automatically make an application secure.

Important controls include:

- Use trusted base images.
- Pin production image references by digest.
- Avoid unnecessary packages.
- Run processes as non-root users where possible.
- Avoid privileged containers.
- Restrict Linux capabilities.
- Apply seccomp and appropriate security profiles.
- Use read-only filesystems where practical.
- Protect registry credentials.
- Restrict exposed ports.
- Use read-only mounts for configuration.
- Apply CPU and memory limits.
- Keep Docker Engine and host systems updated.
- Inspect image provenance and vulnerabilities.
- Protect access to the Docker daemon.

Access to the Docker daemon can provide extensive control over the host. Docker socket access must therefore be treated as a privileged security boundary.

Environment variables are convenient for configuration but should not be treated as a secure secret-management mechanism.

Production systems should use appropriate secret-management facilities.

## 16. Implementation Limitations

The implementations are educational management models, not replacements for Docker Engine.

Specific limitations include:

| Area | Limitation |
|---|---|
| Python | Simulates image and container management unless real CLI inspection is requested |
| JavaScript | Uses in-memory registry and lifecycle simulation |
| C++17 | Does not communicate with a real Docker daemon |
| Java 17 | Models enterprise deployment without launching actual processes |
| PostgreSQL | Maintains management metadata rather than executing Docker operations |

The simulated container states are intentionally simplified.

Real Docker behavior also involves:

- Process exit codes.
- Restart policies.
- Health checks.
- Runtime failures.
- Network namespaces.
- Mount propagation.
- Image platform selection.
- Multi-stage builds.
- Container logging drivers.
- Docker Compose.
- Build cache management.
- Container orchestration.

The SQL schema provides management-level resource checks. It does not provide complete concurrency-safe scheduling or host-wide port allocation across multiple independent Docker daemons.

The educational registry models do not implement the complete OCI image distribution protocol or cryptographic signature verification.

## 17. Practical Learning Outcomes

The five implementations connect Docker concepts to executable software engineering mechanisms.

| Learning area | Technical implementation |
|---|---|
| Architecture | Component and responsibility modeling |
| Images | Immutable manifests and layers |
| Containers | Explicit lifecycle state transitions |
| Registries | Authentication and image distribution |
| Networking | Host and container port mappings |
| Storage | Volume and mount configuration |
| Resource control | CPU and memory policy evaluation |
| Automation | CLI execution and asynchronous operations |
| Observability | Events, inspection and audit records |
| Persistence | JSON inventory and relational storage |
| Security | Input validation and access controls |
| Testing | Invalid transitions and policy failures |

The central operational relationship is:

    Dockerfile
       |
       v
    Image Build
       |
       v
    Docker Image
       |
       v
    Registry Push
       |
       v
    Registry Pull
       |
       v
    Container Creation
       |
       v
    Configuration
       |
       v
    Container Execution
       |
       v
    Monitoring and Lifecycle Management

This relationship connects image construction, distribution, execution, resource management and persistent operational records into one coherent Docker workflow.
