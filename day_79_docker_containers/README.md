# Docker Containers: Lifecycle, Networking, Environment Variables, Volumes and Execution

## 1. Technical Scope

Docker containers provide an isolated execution environment for applications. They package an application and its runtime dependencies while sharing the host operating system kernel.

A container is created from an image. The image contains the filesystem layers, application files, libraries, and configuration required to start the application.

The Docker Engine manages container creation, execution, isolation, networking, storage, and resource allocation.

This implementation examines Docker through five complementary perspectives:

| Implementation | Engineering perspective |
|---|---|
| Python | Operational automation using the Docker CLI |
| JavaScript | Asynchronous container operations and event-driven lifecycle management |
| C++17 | Container domain modeling and governance |
| Java 17 | Enterprise deployment policies and state management |
| PostgreSQL | Persistent operational inventory, auditing, and deployment evaluation |

The implementations use realistic container scenarios involving Nginx, PostgreSQL, resource allocation, application configuration, networking, and persistent storage.

## 2. Docker Architecture

Docker follows a client-server architecture.

The Docker client communicates with the Docker daemon through the Docker Engine API. The daemon manages images, containers, networks, and volumes.

The principal components are:

| Component | Responsibility |
|---|---|
| Docker Client | Sends commands to the Docker Engine |
| Docker Daemon | Manages Docker objects and execution |
| Docker Engine API | Provides communication between clients and the daemon |
| Docker Image | Read-only application template |
| Docker Container | Executable instance of an image |
| Docker Network | Provides communication between containers and external systems |
| Docker Volume | Provides persistent storage |
| Docker Registry | Stores and distributes images |

### Architecture diagram

    User or Application
           |
           v
       Docker CLI
           |
           v
      Docker API
           |
           v
      Docker Daemon
           |
     +-----+------+----------------+
     |            |                |
     v            v                v
   Images      Containers       Networks
                  |
                  v
               Volumes
                  |
                  v
             Host Storage

The Docker daemon performs the operations requested by the client. The container process executes within the isolation mechanisms provided by the operating system.

## 3. Docker Images and Containers

### 3.1 Docker Images

An image is a packaged filesystem and configuration template.

An image contains the files and dependencies needed to initialize a container.

Images are constructed using layers. Each layer represents filesystem changes, and multiple images can share common layers.

For example:

- `nginx:alpine` provides a lightweight Nginx environment.
- `postgres:16-alpine` provides a PostgreSQL environment.
- `python:3.13-slim` provides a lightweight Python runtime.

Image commands:

| Command | Purpose |
|---|---|
| `docker images` | List local images |
| `docker pull nginx:alpine` | Download an image |
| `docker inspect nginx:alpine` | Inspect image configuration |
| `docker image history nginx:alpine` | Examine image layers |
| `docker image rm nginx:alpine` | Remove an image |

An image should preferably be referenced using a specific version or immutable digest rather than an uncontrolled `latest` tag.

### 3.2 Docker Containers

A container is a runtime instance created from an image.

A single image can create multiple containers with independent runtime configurations.

For example:

    nginx:alpine
         |
         +------ web-01
         |
         +------ web-02
         |
         +------ web-03

All three containers originate from the same image but have independent process states, network identities, and writable container layers.

The image remains unchanged when application processes modify the container's writable filesystem layer.

Changes in that writable layer are not automatically incorporated into the original image.

## 4. Container Lifecycle

Container lifecycle management describes the transitions between operational states.

### 4.1 Principal States

| State | Meaning |
|---|---|
| Created | Container exists but its main process has not started |
| Running | Main container process is executing |
| Paused | Container processes are suspended |
| Restarting | Container is undergoing a restart operation |
| Exited | Main container process has stopped |
| Dead | Container has entered an unrecoverable runtime state |

A container's lifecycle state is different from the availability of its application.

A running container does not necessarily mean that its application is healthy.

### 4.2 Lifecycle workflow

    Image
      |
      v
    docker create
      |
      v
    CREATED
      |
      v
    docker start
      |
      v
    RUNNING
      |
      +------ docker pause ------> PAUSED
      |                              |
      |                         docker unpause
      |                              |
      |<-----------------------------+
      |
      +------ docker restart
      |
      v
    RESTARTING
      |
      v
    RUNNING
      |
      +------ docker stop ------> EXITED
      |
      +------ unrecoverable ----> DEAD

A stopped container can generally be restarted. Removing a container is a separate operation.

### 4.3 Lifecycle commands

| Command | Operation |
|---|---|
| `docker create nginx:alpine` | Create a container without starting it |
| `docker start container-name` | Start an existing container |
| `docker run nginx:alpine` | Create and start a container |
| `docker pause container-name` | Suspend container processes |
| `docker unpause container-name` | Resume container processes |
| `docker restart container-name` | Restart a container |
| `docker stop container-name` | Gracefully stop a container |
| `docker kill container-name` | Immediately terminate the main process |
| `docker rm container-name` | Remove a stopped container |
| `docker rm -f container-name` | Force-remove a container |

The `docker run` command combines container creation and startup.

The `docker create` and `docker start` commands separate those operations.

### 4.4 Graceful Shutdown

Docker normally sends a termination signal to the container's main process and waits for the configured timeout.

If the process does not stop within the timeout, Docker can forcefully terminate it.

For example:

`docker stop --time 10 web-01`

Graceful shutdown is important for applications that need to:

- Finish active requests.
- Close database connections.
- Flush buffered writes.
- Complete transactions.
- Release application resources.

The application must handle termination signals correctly for graceful shutdown to work as intended.

### 4.5 Restart Policies

Restart policies define how Docker responds when a container exits.

| Policy | Behaviour |
|---|---|
| `no` | Do not automatically restart |
| `always` | Restart whenever the container exits, subject to daemon and manual-stop behaviour |
| `unless-stopped` | Restart unless explicitly stopped by the operator |
| `on-failure` | Restart when the container exits with a non-zero status |

Example:

`docker run -d --restart unless-stopped nginx:alpine`

Restart policies provide process-level recovery. They do not establish application correctness or guarantee service availability.

## 5. Container Execution

A container executes a process using the configuration inherited from its image and the runtime settings supplied during creation.

The main container process is important because its termination normally causes the container to exit.

### 5.1 Interactive Execution

`docker run -it ubuntu:24.04 bash`

The `-i` option keeps standard input available.

The `-t` option allocates a terminal.

This configuration is useful for interactive troubleshooting.

### 5.2 Detached Execution

`docker run -d --name web-01 nginx:alpine`

The `-d` option starts the container in the background and returns control to the terminal.

### 5.3 Executing Commands in an Existing Container

`docker exec -it web-01 sh`

This starts an additional process inside an existing running container.

It does not replace the original main process.

### 5.4 Container Inspection

`docker inspect web-01`

Inspection exposes detailed runtime configuration, including:

- Container identifier.
- Image reference.
- Environment configuration.
- Network attachments.
- Mount information.
- Resource configuration.
- Process state.
- Health-check information.

Inspection output may contain sensitive environment values. It should not be copied into unrestricted logs.

### 5.5 Container Logs

`docker logs web-01`

Additional options:

- `--tail 100` limits the displayed number of recent lines.
- `-f` follows new log entries.
- `--timestamps` includes timestamps.

The logging driver and application logging behaviour influence which output is retained and how it can be retrieved.

## 6. Environment Variables

Environment variables provide runtime configuration without requiring application source-code changes.

They are commonly used for:

- Application environment selection.
- Service ports.
- Database hostnames.
- Database names.
- Logging levels.
- Feature configuration.
- Runtime behaviour.

### 6.1 Setting Environment Variables

Example:

`docker run -d --name web-01 -e APP_ENV=production -e APP_PORT=80 nginx:alpine`

The application receives these variables through its process environment.

### 6.2 Environment Files

A configuration file can be supplied through:

`docker run --env-file app.env nginx:alpine`

An environment file may contain:

    APP_ENV=production
    APP_PORT=80
    LOG_LEVEL=info

Environment variables should be separated from application logic.

### 6.3 Configuration Versus Secrets

Environment variables are not automatically encrypted secrets.

They may be accessible through container inspection, process information, diagnostic output, or privileged host access.

Production systems should use an appropriate secret-management mechanism.

Sensitive values should not be:

- Hardcoded into application source code.
- Committed to version control.
- Printed in logs.
- Included in unrestricted inspection reports.
- Exposed through public application endpoints.

The PostgreSQL implementation distinguishes sensitive and non-sensitive environment records and masks sensitive values in its reporting query.

## 7. Docker Networking

Docker networking enables communication between containers, hosts, and external systems.

Containers attached to the same suitable network can communicate using their network addresses and, on user-defined Docker networks, container names or configured aliases.

### 7.1 Network Drivers

| Driver | Purpose |
|---|---|
| Bridge | Connects containers through a virtual bridge |
| Host | Uses the host network namespace |
| None | Provides no ordinary container network connectivity |
| Overlay | Connects services across multiple Docker hosts in supported configurations |
| Macvlan | Gives containers addresses on a physical network segment |

### 7.2 Bridge Networking

A bridge network is commonly used for applications running on one Docker host.

Create a network:

`docker network create application-network`

Run a container:

`docker run -d --name web-01 --network application-network nginx:alpine`

Inspect the network:

`docker network inspect application-network`

Connect another container:

`docker run -d --name app-01 --network application-network python:3.13-slim`

Containers attached to the same user-defined bridge network can communicate using their container names.

### 7.3 Port Publishing

Port publishing exposes a container port through a host port.

Example:

`docker run -d -p 8080:80 nginx:alpine`

The mapping is:

    Host machine
       |
       | TCP port 8080
       |
       v
    Container
       |
       | TCP port 80
       |
       v
    Nginx application

The host can access the service through `localhost:8080` when running on the same machine.

A port mapping does not change the application's listening port inside the container.

### 7.4 Restricting Port Exposure

Example:

`docker run -d -p 127.0.0.1:8080:80 nginx:alpine`

Binding to loopback restricts access to the host's local interface rather than publishing the port on every host interface.

The exact exposure behaviour also depends on the Docker networking implementation and host firewall configuration.

### 7.5 Container-to-Container Communication

Consider a web application and PostgreSQL database.

    Web Application
         |
         | application-network
         |
         v
      PostgreSQL

The application connects using the database container's network name.

For example:

    DB_HOST=database-postgres
    DB_PORT=5432

Publishing the PostgreSQL port to the host is not necessary for communication between containers on the same suitable network.

A separate internal database network can reduce unnecessary external exposure.

### 7.6 Network Management

| Command | Purpose |
|---|---|
| `docker network ls` | List networks |
| `docker network create app-network` | Create a network |
| `docker network inspect app-network` | Inspect a network |
| `docker network connect app-network web-01` | Attach a container |
| `docker network disconnect app-network web-01` | Detach a container |
| `docker network rm app-network` | Remove a network |

Networks should be removed only after their dependent containers have been disconnected.

## 8. Docker Volumes and Persistent Storage

Containers have a writable filesystem layer. This layer is associated with the container lifecycle.

Removing a container normally removes its writable layer.

Persistent application data should therefore be stored outside that layer.

Docker provides named volumes, anonymous volumes, and bind mounts.

### 8.1 Named Volumes

A named volume is managed by Docker and can be reused across containers.

Create:

`docker volume create postgres-data`

Use:

`docker run -d --name database -v postgres-data:/var/lib/postgresql/data postgres:16-alpine`

The volume stores database files independently of the container's writable layer.

Removing the container does not automatically remove the named volume.

### 8.2 Bind Mounts

A bind mount connects a host filesystem path to a container path.

Example:

`docker run -d --name web -v /opt/web-content:/usr/share/nginx/html:ro nginx:alpine`

The host directory becomes accessible inside the container.

The `ro` option makes the mount read-only from the container's perspective.

Bind mounts are useful for:

- Development source-code sharing.
- Configuration files.
- Host-managed datasets.
- Explicit filesystem integration.

Host paths must be validated because a bind mount can expose sensitive host files.

### 8.3 Anonymous Volumes

Anonymous volumes are created without an explicitly assigned reusable volume name.

They can be useful for image-defined storage locations, although their lifecycle and cleanup should be managed deliberately.

### 8.4 Volume Comparison

| Feature | Named volume | Bind mount | Anonymous volume |
|---|---|---|---|
| Managed by Docker | Yes | No | Yes |
| Explicit name | Yes | Host path | Usually generated |
| Host path control | Docker-managed | Operator-managed | Docker-managed |
| Persistence after container removal | Yes, normally | Yes | Yes, normally |
| Common use | Database storage | Development and host integration | Image-defined storage |

### 8.5 Volume Commands

| Command | Purpose |
|---|---|
| `docker volume create app-data` | Create a named volume |
| `docker volume ls` | List volumes |
| `docker volume inspect app-data` | Inspect volume details |
| `docker volume prune` | Remove unused anonymous and named volumes subject to command options and confirmation |
| `docker volume rm app-data` | Remove a volume |

Volume removal should be treated as a potentially destructive operation.

A database volume should not be deleted merely because its associated container is stopped or removed.

### 8.6 Data Persistence

    Container A
        |
        v
    Named Volume
        |
        v
    Persistent Data
        |
        v
    Container B

The same volume can be mounted by a replacement container.

This enables container replacement without automatically discarding application data.

Persistent storage is not a substitute for backups. A backup strategy must address consistency, recovery, retention, and restoration testing.

## 9. Container Resource Management

Containers can be assigned CPU and memory limits.

These limits help prevent one application from consuming all host resources.

### 9.1 Memory Limits

Example:

`docker run -d --memory 256m nginx:alpine`

The container receives a memory limit of approximately 256 MiB.

When memory pressure exceeds the configured constraints, the container process may be terminated by the operating system's out-of-memory handling.

### 9.2 CPU Limits

Example:

`docker run -d --cpus 1.5 nginx:alpine`

This limits the container's CPU usage to approximately 1.5 CPU cores under Docker's CPU quota configuration.

CPU limits constrain resource consumption rather than reserving dedicated physical processors.

### 9.3 Monitoring

Useful commands include:

- `docker stats`
- `docker stats --no-stream`
- `docker inspect`
- `docker ps -a`

Operational monitoring should consider CPU consumption, memory usage, process health, restart frequency, and application response behaviour.

## 10. Health Checks

A health check evaluates whether an application is functioning as expected.

Container state and application health are separate concepts.

For example:

| Container state | Health status | Interpretation |
|---|---|---|
| Running | Healthy | Application is responding |
| Running | Unhealthy | Container process runs but application checks fail |
| Running | Starting | Health evaluation is still in progress |
| Exited | Not applicable | Main process has stopped |

An image or container configuration can define a health check.

A typical health-check configuration uses:

- Test command.
- Interval.
- Timeout.
- Retry count.
- Start period.

Health checks can detect failures that a simple running-state check cannot identify.

A health check does not automatically provide complete recovery. Monitoring and orchestration policies must determine what action follows a failure.

## 11. Docker Security

Container isolation does not mean that a container is equivalent to a separate physical machine.

Containers share the host kernel, making host security important.

### 11.1 Image Security

- Use trusted image publishers.
- Prefer specific version tags or immutable digests.
- Review image provenance.
- Scan images for vulnerabilities.
- Remove unnecessary packages.
- Rebuild images when security updates are required.

### 11.2 Runtime Security

- Avoid privileged containers.
- Run applications as non-root users where possible.
- Apply CPU and memory limits.
- Restrict published ports.
- Use read-only root filesystems when practical.
- Drop unnecessary Linux capabilities.
- Apply appropriate seccomp and security profiles.
- Restrict access to the Docker daemon.

### 11.3 Storage Security

- Avoid mounting sensitive host directories.
- Use read-only mounts where possible.
- Restrict volume access.
- Protect database credentials.
- Back up persistent data.
- Separate application data from container runtime files.

### 11.4 Docker Socket Security

The Docker daemon socket provides powerful control over the Docker host.

Unrestricted access to the socket can effectively grant extensive host-level privileges.

Mounting `/var/run/docker.sock` into an application container should therefore be treated as a significant security decision.

## 12. Python Implementation

File: `docker_container_manager.py`

The Python implementation is an operational automation tool that communicates with the actual Docker Engine through the Docker CLI.

### Main components

| Component | Responsibility |
|---|---|
| `DockerClient` | Executes Docker commands |
| `ContainerConfig` | Stores container configuration |
| `PortMapping` | Validates host and container ports |
| `ContainerManager` | Coordinates deployment and lifecycle operations |
| `ContainerState` | Represents runtime states |
| `DockerError` | Handles operational failures |

### Implemented operations

- Docker daemon verification.
- Image inspection and pulling.
- Container creation.
- Container execution.
- Container inspection.
- Starting and stopping.
- Pausing and resuming.
- Restarting.
- Log retrieval.
- Container inventory.
- Network creation.
- Volume creation.
- Health inspection.
- Resource monitoring.
- Configuration validation.

### Engineering decisions

The implementation uses `subprocess.run()` with an argument list and `shell=False`.

This avoids shell interpretation of dynamically supplied arguments.

The implementation validates names, ports, environment variable keys, restart policies, and resource constraints before executing Docker commands.

The `--demo` option uses an Nginx container with resource limits and port publishing.

The `--test` option tests configuration validation without requiring a running Docker daemon.

The implementation is a single-host operational manager. It does not implement distributed orchestration, image signing verification, or automatic rollback.

## 13. JavaScript Implementation

File: `docker_manager.js`

The JavaScript implementation uses Node.js asynchronous programming and event-driven lifecycle management.

### Main components

| Component | Responsibility |
|---|---|
| `DockerClient` | Executes asynchronous Docker commands |
| `ContainerConfig` | Validates deployment configuration |
| `ContainerStateMachine` | Controls permitted state transitions |
| `ContainerService` | Coordinates deployments |
| `EventEmitter` | Publishes operational events |
| `DockerError` | Represents operational failures |

### Event-driven architecture

The implementation publishes events such as:

- `imagePullStarted`
- `imagePullCompleted`
- `containerStarted`
- `containerStateChanged`
- `containerStopped`
- `deploymentFailed`

The event system separates lifecycle state management from operational reporting.

### Asynchronous execution

The Docker CLI is executed using Node.js `spawn()`.

The implementation avoids `shell: true`, applies command timeouts, and limits captured output.

Promises provide asynchronous command completion and failure propagation.

The container registry uses a `Map` for named state-machine lookup.

The `Set` data structure is used to validate unique host ports.

The `test` command exercises state transitions and configuration validation without contacting Docker.

The JavaScript implementation is particularly useful for event-driven operational services and asynchronous management applications.

## 14. C++17 Implementation

File: `docker_engine.cpp`

The C++ implementation models container management as a domain-oriented system.

It focuses on explicit state transitions, data validation, resource constraints, and deployment eligibility.

### Main domain structures

| Structure or class | Responsibility |
|---|---|
| `Container` | Represents a container |
| `Repository` | Maintains container, network, and volume inventories |
| `ResourceLimits` | Validates CPU and memory |
| `Environment` | Manages environment variables |
| `PortMapping` | Models published ports |
| `Volume` | Represents a storage attachment |
| `Network` | Represents network configuration |
| `HealthCheck` | Evaluates health results |
| `DeploymentResult` | Reports eligibility and violations |

### Container repository

The `Repository` maintains:

- Containers in a `map`.
- Networks in a `map`.
- Volume names in a `set`.

This provides efficient lookup and uniqueness checks.

### Lifecycle enforcement

The `Container` class controls legal transitions.

Invalid transitions generate exceptions instead of silently changing state.

For example, a running container cannot directly transition back to the created state.

### Deployment evaluation

The deployment evaluator checks:

- Running state.
- Health status.
- Privileged execution.
- Filesystem configuration.

The implementation also separates errors from warnings.

This distinction is important because some conditions must block deployment while others should be visible for operational review.

The C++ implementation is an in-memory governance model rather than a Docker Engine API client.

## 15. Java 17 Implementation

File: `DockerEnterprise.java`

The Java implementation presents an enterprise-oriented deployment-management architecture.

It uses explicit domain types, immutable configuration objects, service classes, and deployment policies.

### Main components

| Component | Responsibility |
|---|---|
| `ContainerConfiguration` | Immutable deployment configuration |
| `ManagedContainer` | Container identity and lifecycle |
| `ContainerRegistry` | Central container inventory |
| `DeploymentService` | Deployment orchestration |
| `DeploymentPolicy` | Runtime security and resource rules |
| `HealthMonitor` | Health-state evaluation |
| `ResourceAllocation` | CPU and memory constraints |
| `NetworkConfiguration` | Network domain model |

### Immutable configuration

Java records represent value objects such as:

- Port mappings.
- Resource allocations.
- Volume mounts.
- Network configuration.
- Deployment policies.

The configuration object uses immutable collections through `List.copyOf()` and `Map.copyOf()`.

This prevents unexpected modification after deployment validation.

### Enterprise policy evaluation

The production deployment policy enforces:

- No privileged execution.
- Read-only root filesystem.
- CPU limits.
- Memory limits.
- Published-port limits.
- Health-check requirements.

Policy violations prevent registration and deployment.

### State management

The `ManagedContainer` class enforces lifecycle transitions through synchronized methods.

The registry protects its container inventory through synchronized operations.

This provides a basic thread-safe in-memory model, although a production service would also require distributed coordination, persistence, and reconciliation with the Docker Engine.

### Health and eligibility

Health evaluation is separate from container execution.

The deployment eligibility service checks whether a container is running and has achieved a healthy status when health checks are mandatory.

## 16. PostgreSQL Implementation

File: `docker_management.sql`

The PostgreSQL implementation models Docker operations as a relational operational inventory.

It supports historical tracking, deployment policy evaluation, and operational reporting.

### Relational domain model

    Docker Hosts
         |
         +------ Docker Images
         |
         +------ Docker Networks
         |
         +------ Docker Volumes
         |
         +------ Docker Containers
                       |
          +------------+-------------+
          |            |             |
          v            v             v
       Ports      Environment     Lifecycle
          |            |             |
          v            v             v
       Network      Sensitive     Health Checks
      Attachments   Configuration
          |
          v
       Volume Mounts

          |
          v
    Deployment Requests
          |
          v
    Deployment Policies
          |
          v
    Eligibility Evaluation
          |
          v
    Deployment Decision

### Main tables

| Table | Purpose |
|---|---|
| `docker_hosts` | Host infrastructure inventory |
| `docker_images` | Image metadata |
| `docker_networks` | Network definitions |
| `docker_volumes` | Persistent storage definitions |
| `docker_containers` | Container inventory |
| `container_environment` | Runtime environment configuration |
| `container_ports` | Published port mappings |
| `container_network_attachments` | Network membership |
| `container_volume_mounts` | Persistent storage attachments |
| `container_health_checks` | Health history |
| `container_lifecycle_events` | State-transition history |
| `deployment_policies` | Deployment rules |
| `deployment_requests` | Deployment decisions |

### Referential integrity

Foreign keys maintain relationships between containers, hosts, images, networks, volumes, and deployment policies.

Unique constraints prevent duplicate host names, container names within a host, and conflicting configuration records.

Check constraints enforce valid ports, resource allocations, and environment variable names.

### Lifecycle triggers

The `validate_container_transition()` function rejects invalid state transitions.

The `record_container_lifecycle()` function records state changes and maintains relevant timestamps.

This ensures that lifecycle changes made through ordinary SQL updates are audited.

### Deployment evaluation

The `evaluate_deployment()` function evaluates a deployment request against its assigned policy.

It checks:

- Container running state.
- Privileged execution.
- Read-only filesystem requirements.
- CPU allocation.
- Memory allocation.
- Trusted image status.
- Published-port limits.
- Health status.

The `process_deployment()` procedure stores an approval or rejection decision.

### Reporting

The SQL script provides reports for:

- Container inventory.
- Environment configuration with sensitive-value masking.
- Network topology.
- Volume attachments.
- Latest health status.
- Host resource allocation.
- Lifecycle history.
- Deployment decisions.
- Container-state distribution.
- Image usage.
- Deployment statistics.
- Deployment readiness.

### Database security considerations

The environment table contains potentially sensitive values.

The reporting query masks sensitive values, but masking in a query is not equivalent to access control.

Production deployments should use restricted PostgreSQL roles, external secret-management systems, and appropriate permissions on sensitive tables and functions.

The database represents recorded operational state. It does not directly control Docker containers. A production integration must reconcile database records with actual Docker Engine observations.

## 17. Operational Workflow

The following workflow combines the concepts implemented across the five source files.

### Step 1: Verify Docker

Confirm that the Docker CLI and daemon are available.

`docker version`

`docker info`

### Step 2: Obtain an Image

`docker pull nginx:alpine`

### Step 3: Create Persistent Storage

`docker volume create nginx-data`

### Step 4: Create an Application Network

`docker network create application-network`

### Step 5: Execute the Container

`docker run -d --name web-nginx --network application-network -p 8088:80 --memory 128m --cpus 0.5 -v nginx-data:/usr/share/nginx/html:ro -e APP_ENV=production --restart unless-stopped nginx:alpine`

### Step 6: Inspect the Container

`docker inspect web-nginx`

### Step 7: Examine Logs

`docker logs --tail 50 web-nginx`

### Step 8: Monitor Resources

`docker stats --no-stream web-nginx`

### Step 9: Stop and Restart

`docker stop web-nginx`

`docker start web-nginx`

### Step 10: Remove the Container

`docker stop web-nginx`

`docker rm web-nginx`

The named volume and network remain separate Docker objects and require their own lifecycle management.

## 18. Failure Conditions and Recovery

| Failure | Possible cause | Appropriate response |
|---|---|---|
| Docker daemon unavailable | Engine is stopped | Start the Docker service |
| Image pull failure | Registry unavailable or authentication failure | Verify registry access |
| Container name conflict | Existing container uses the name | Inspect or remove the existing container |
| Port allocation failure | Host port already occupied | Select another host port |
| Container exits immediately | Main process terminates | Inspect logs and exit code |
| Health check failure | Application is unavailable | Inspect application dependencies |
| Volume permission failure | Incorrect ownership or permissions | Validate host and container permissions |
| Container cannot reach another service | Incorrect network attachment | Inspect network membership |
| Out-of-memory termination | Insufficient memory limit | Investigate usage and adjust limits |
| Restart loop | Application repeatedly fails | Inspect restart count, logs, and startup dependencies |
| Image security failure | Untrusted or vulnerable image | Reject deployment and review the image |

Failure handling should distinguish between Docker Engine failures, container process failures, and application-level failures.

## 19. Performance Considerations

### Images

Use smaller images when practical.

Reducing unnecessary packages decreases image transfer size and may reduce the attack surface.

### Storage

Use named volumes for persistent application data.

Avoid unnecessary writes to the container writable layer.

### Networking

Use appropriate user-defined networks and avoid publishing ports that do not need external access.

### Resource allocation

Apply realistic CPU and memory limits.

Monitor actual workload consumption before changing allocations.

### Database

The PostgreSQL implementation uses indexes on frequently filtered columns, including container state, host identifiers, lifecycle timestamps, and deployment status.

Indexes improve retrieval performance but increase storage and write-maintenance costs.

### Application management

Avoid excessive inspection and polling operations.

Cache suitable metadata and use event-driven updates where available.

## 20. Limitations and Engineering Boundaries

The five implementations intentionally serve different purposes.

| Implementation | Actual execution model | Principal limitation |
|---|---|---|
| Python | Executes real Docker CLI commands | Single-host operational automation |
| JavaScript | Executes real Docker CLI commands asynchronously | Local registry and limited lifecycle coordination |
| C++17 | Simulates container management | Does not call Docker Engine |
| Java 17 | Simulates enterprise deployment governance | In-memory state rather than distributed persistence |
| PostgreSQL | Stores and evaluates operational records | Requires external synchronization with Docker |

The Python and JavaScript programs interact with Docker when executed in an environment with an available Docker daemon.

The C++17 and Java 17 programs demonstrate domain modeling and governance rules without creating real containers.

The PostgreSQL implementation models operational data and deployment decisions. It does not independently start, stop, or inspect containers.

The Docker Engine remains the authoritative source of actual runtime state.

A production management system would require periodic reconciliation between the Docker Engine and its operational database.

## 21. Key Technical Distinctions

| Concept | What it represents | What it does not guarantee |
|---|---|---|
| Image | Application execution template | Running application |
| Container | Runtime instance | Application health |
| Running state | Main process is executing | Service availability |
| Health check | Application-level condition assessment | Automatic recovery |
| Network | Communication configuration | Application authorization |
| Port publishing | Host-to-container port exposure | Secure external access |
| Named volume | Persistent Docker-managed storage | Backup and disaster recovery |
| Environment variable | Runtime configuration | Secret confidentiality |
| Restart policy | Container restart behaviour | Successful application recovery |
| Resource limit | Runtime resource constraint | Performance guarantees |
| Deployment policy | Operational acceptance rules | Actual runtime enforcement without integration |

Understanding these distinctions is essential for designing reliable container-based application systems.
