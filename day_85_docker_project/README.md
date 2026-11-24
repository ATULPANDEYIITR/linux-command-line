# Docker Multi-Service Application

## Project Overview

This project demonstrates how to containerize and operate a multi-service application using Docker and Docker Compose.

The application consists of three primary services:

1. Frontend: Node.js application that serves the user interface and forwards API requests.
2. Backend: Python REST API that implements application operations and database access.
3. Database: PostgreSQL relational database that stores application records.

The architecture also includes Docker networks, persistent storage, container health checks, service dependencies, deployment validation, and operational monitoring.

The five implementations provide different technical perspectives on containerized application management.

## 1. Application Architecture

<escape>
                 USER / BROWSER
                       |
                       |
                 localhost:3000
                       |
                       v
              +------------------+
              |     FRONTEND     |
              |     Node.js      |
              |     Port 3000    |
              +------------------+
                       |
                       |
                 HTTP API Proxy
                       |
                       v
              +------------------+
              |     BACKEND      |
              |     Python       |
              |     Port 8000    |
              +------------------+
                       |
                       |
                  SQL / TCP
                       |
                       v
              +------------------+
              |    POSTGRESQL    |
              |     Port 5432    |
              +------------------+
                       |
                       |
                 Persistent Volume
                       |
                       v
                 postgres_data
</escape>

The frontend is the browser-facing service. It forwards application requests to the backend.

The backend processes requests, validates input, and communicates with PostgreSQL.

The database stores application records independently of the lifecycle of its container.

### Service configuration

| Service | Technology | Container port | Responsibility |
|---|---|---:|---|
| Frontend | Node.js | 3000 | User interface and API forwarding |
| Backend | Python | 8000 | REST API and business operations |
| Database | PostgreSQL 17 | 5432 | Persistent relational storage |

The host exposes ports 3000 and 8000 on the loopback interface. PostgreSQL is not published to the host.

The frontend is available at `http://localhost:3000`.

The backend health endpoint is available at `http://localhost:8000/health`.

## 2. Docker Fundamentals

### Containerization

Containerization packages an application and its runtime dependencies into an isolated execution environment.

A container uses an image as its starting point.

A Docker image contains:

- Application source files.
- Runtime dependencies.
- Required system libraries.
- Environment defaults.
- Startup instructions.

A container is a running instance of an image.

The distinction is important:

| Docker concept | Meaning |
|---|---|
| Image | Immutable application template |
| Container | Runtime instance of an image |
| Dockerfile | Instructions for building an image |
| Registry | Storage and distribution of images |
| Volume | Persistent or separately managed storage |
| Network | Communication between containers |
| Compose | Definition and management of related services |

An image can be used to create multiple containers. Containers can be stopped, removed, and recreated without rebuilding the underlying application.

### Dockerfile

Each application service has its own Dockerfile.

The backend image uses Python 3.13 on a slim Linux base.

The frontend image uses Node.js 22 on Alpine Linux.

The database uses the official PostgreSQL 17 Alpine image.

The backend Dockerfile follows these stages:

1. Select the runtime image.
2. Define the working directory.
3. Create an unprivileged application user.
4. Copy dependency definitions.
5. Install dependencies.
6. Copy application files.
7. Switch to the unprivileged user.
8. Expose the application port.
9. Define the startup command.

The dependency installation step occurs before copying application source. This supports Docker layer caching when source files change without dependency changes.

### Image layers and caching

Docker builds images using layers.

A change to an earlier Dockerfile instruction can invalidate subsequent cached layers.

The dependency-first copy strategy reduces unnecessary package installation during development.

Image size also affects:

- Build duration.
- Registry transfer time.
- Deployment speed.
- Storage requirements.
- Security scanning workload.

Minimal base images reduce unnecessary packages but can introduce compatibility constraints.

## 3. Docker Compose

Docker Compose defines and manages multiple related containers through a declarative YAML configuration.

The project's `compose.yaml` defines:

- Three services.
- Two bridge networks.
- One persistent volume.
- Build contexts.
- Environment variables.
- Port mappings.
- Health checks.
- Restart policies.
- Startup dependencies.
- Security options.

### Service definitions

The database service uses the official PostgreSQL image.

The backend is built from the local backend directory.

The frontend is built from the local frontend directory.

Compose uses service names as internal DNS names.

For example:

- The backend accesses PostgreSQL using `database:5432`.
- The frontend accesses the backend using `backend:8000`.

The service name is preferable to a hardcoded container IP address because Docker manages service discovery when container addresses change.

### Service dependencies

The application has the following dependency graph:

<escape>
database
   |
   v
backend
   |
   v
frontend
</escape>

The database must become healthy before the backend starts.

The backend must become healthy before the frontend starts.

The `depends_on` configuration uses `condition: service_healthy`.

This is more meaningful than merely checking whether a container has started.

A running PostgreSQL container does not necessarily mean PostgreSQL is ready to accept database connections.

The database health check uses `pg_isready`.

The backend health check calls its HTTP health endpoint.

The frontend health check verifies its HTTP response.

Startup dependencies do not provide continuous dependency monitoring. Applications must still handle failures occurring after startup.

## 4. Docker Networking

Docker networking provides communication between containers.

This project defines two bridge networks.

| Network | Services | Purpose |
|---|---|---|
| public | Frontend, backend | Application-facing communication |
| internal | Frontend, backend, database | Internal service communication |

The backend connects to both networks.

The frontend also connects to both networks.

The database connects only to the internal network.

This prevents direct network exposure of the database through the public application network.

### Bridge networking

A bridge network provides isolated communication among containers attached to it.

Docker supplies internal DNS resolution.

For example, the backend does not need the database container's current IP address.

It uses:

`DB_HOST=database`

Docker resolves that service name within the shared network.

### Host ports and container ports

A port mapping connects a host port to a container port.

For example:

| Host | Container | Service |
|---:|---:|---|
| 3000 | 3000 | Frontend |
| 8000 | 8000 | Backend |
| Not published | 5432 | Database |

The frontend and backend mappings bind to `127.0.0.1`.

This restricts host access to the local machine rather than exposing these ports on every host network interface.

The database does not need a host port mapping for communication with the backend.

Containers use their internal network addresses and container ports.

### Network security

Network isolation is one security layer, not a replacement for authentication or authorization.

Production deployments should also consider:

- Database authentication.
- Encrypted external connections.
- Restricted service permissions.
- Firewall rules.
- Secret management.
- Network segmentation.
- Audit logging.

## 5. Persistent Storage

Containers are designed to be replaceable.

Data stored only in a container's writable filesystem can disappear when the container is removed.

The project uses a named Docker volume:

`postgres_data`

The volume is mounted at:

`/var/lib/postgresql/data`

This is PostgreSQL's database storage directory.

### Volume lifecycle

<escape>
Docker Container
      |
      v
PostgreSQL Data Directory
      |
      v
Named Docker Volume
      |
      v
Host-managed persistent storage
</escape>

The database container can be recreated without intentionally removing its named volume.

The following operations have different consequences:

| Operation | Container | Volume |
|---|---|---|
| Stop | Stops | Preserved |
| Start | Restarts | Reused |
| Restart | Restarts | Preserved |
| Remove container | Removed | Preserved |
| Compose down | Removed | Preserved |
| Compose down --volumes | Removed | Removed |

Persistent storage is not equivalent to backup.

Production systems should maintain independent backups, test restoration, and consider database replication and recovery requirements.

## 6. Frontend Implementation

The frontend uses Node.js and the built-in HTTP server.

It provides:

- An application landing page.
- A task creation form.
- Task retrieval.
- Backend request forwarding.
- Request-size limits.
- Timeout handling.
- Error responses.
- Graceful shutdown.

The browser communicates with the frontend using relative API paths.

The frontend then forwards the requests to the backend.

This approach avoids requiring the browser to resolve Docker-internal service names.

Docker service names are available inside appropriate container networks, not automatically inside the user's browser.

### API forwarding

The frontend forwards:

- `GET /api/tasks`
- `POST /api/tasks`

The backend URL is supplied through `BACKEND_URL`.

The application uses a request timeout to avoid waiting indefinitely for an unavailable backend.

The circuit breaker prevents repeated requests from continuously reaching a failing service.

Its states are:

| State | Behavior |
|---|---|
| CLOSED | Requests are permitted |
| OPEN | Requests are rejected temporarily |
| HALF_OPEN | One recovery request is permitted |

A successful request resets the failure counter.

A failed request increases the counter.

This improves failure handling during backend outages.

The circuit breaker is maintained in application memory. It is not shared across multiple frontend replicas.

## 7. Backend Implementation

The backend uses Python's standard HTTP server and Psycopg 3.

It exposes three application operations.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Backend and database health |
| GET | `/api/tasks` | Retrieve tasks |
| POST | `/api/tasks` | Create a task |

### Database connectivity

Database configuration is provided through environment variables:

- `DB_HOST`
- `DB_PORT`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`

The backend uses the internal Docker hostname `database`.

Database connections use a connection timeout.

The initialization routine retries temporary connection failures.

This handles cases where the database process is temporarily unavailable.

### Input validation

Task titles must:

- Be strings.
- Contain non-whitespace characters.
- Have between 1 and 200 characters.

Request bodies are limited to 4 KB.

Malformed JSON produces a client error.

Invalid database operations produce an appropriate service error.

### SQL parameterization

The backend uses parameterized SQL statements.

User-supplied values are passed separately from SQL syntax.

This prevents user input from being interpreted as SQL commands.

### Connection management

Database connections use context managers.

Transactions are committed when successful and rolled back when an exception occurs.

For a larger production application, a bounded connection pool is preferable to creating a new database connection for every request.

## 8. PostgreSQL Data Model

The application database contains a `tasks` table.

| Column | Type | Purpose |
|---|---|---|
| id | BIGINT | Primary key |
| title | VARCHAR(200) | Task description |
| completed | BOOLEAN | Completion status |
| created_at | TIMESTAMPTZ | Creation timestamp |

The primary key provides a unique identifier.

The title constraint prevents empty task descriptions.

The creation timestamp records when a task was inserted.

The database initialization script uses `CREATE TABLE IF NOT EXISTS`.

PostgreSQL initialization scripts mounted into `/docker-entrypoint-initdb.d` are executed when the database is first initialized with an empty data directory.

They are not automatically rerun whenever the container restarts.

For evolving production schemas, use explicit database migrations.

## 9. Python Project Manager

The Python implementation provides operational control over the Docker project.

Its `DockerProject` class separates project operations from command-line argument handling.

### Supported operations

| Command | Function |
|---|---|
| `init` | Generate project files |
| `validate` | Validate Compose configuration |
| `up` | Build and start services |
| `status` | Display service status |
| `logs` | Retrieve service logs |
| `down` | Stop and remove containers |
| `clean` | Remove containers and volumes |
| `inspect` | Retrieve Compose container information |

The command runner uses Python's `subprocess` module with argument lists rather than shell-interpolated commands.

This reduces command-injection risks.

The project manager also provides:

- Timeout handling.
- Missing executable detection.
- Return-code validation.
- Backend readiness polling.
- Destructive-operation confirmation.

The `clean` operation requires explicit confirmation because deleting the named volume destroys database data.

## 10. C++17 Topology Validation

The C++ implementation models Docker topology and deployment dependencies.

It uses:

- Classes.
- Structures.
- Enumerations.
- Maps.
- Vectors.
- Queues.
- Sets.
- Standard algorithms.
- Exception handling.

The `DockerTopology` class validates service registration, ports, dependencies, network placement, and persistent storage.

### Dependency graph

Service dependencies are represented as a directed graph.

For example:

<escape>
database -> backend -> frontend
</escape>

A topological sorting algorithm determines a valid startup order.

Kahn's algorithm uses an in-degree map and a queue.

Its time complexity is:

`O(V + E)`

Where:

- `V` represents the number of services.
- `E` represents the number of dependency relationships.

A cycle prevents a valid startup ordering.

The implementation rejects circular dependencies and missing service definitions.

The `DeploymentEngine` models service state transitions and dependency readiness.

Its health-check results are simulated for topology demonstration. It does not communicate with the Docker Engine.

## 11. Java 17 Enterprise Deployment Model

The Java implementation models enterprise deployment governance.

It uses:

- Records for immutable data.
- Enums for controlled states.
- Collections for service registration.
- Service classes for deployment operations.
- Custom exceptions.
- Explicit state transitions.
- Deployment policies.
- Health-monitoring capabilities.

### Deployment policy

The `DeploymentPolicy` record controls:

- Mandatory health checks.
- Persistent database storage.
- Public database restrictions.
- Maximum restart attempts.

### State transitions

A container moves through controlled states.

<escape>
CREATED
   |
   v
STARTING
   |
   v
RUNNING
   |
   v
HEALTHY
   |
   v
UNHEALTHY
   |
   v
FAILED
</escape>

The model rejects invalid transitions.

For example, a newly created container cannot immediately become healthy without passing through startup and running states.

### Enterprise distinction

The Java deployment model separates:

1. Service definitions.
2. Runtime container instances.
3. Deployment policies.
4. Health results.
5. Deployment orchestration.

This separation makes the domain easier to test and extend.

The sample deployment uses simulated health results. The `HealthMonitor` class also demonstrates actual HTTP health checking.

Neither implementation invokes Docker Engine commands directly.

## 12. Service Health and Reliability

Container health checks evaluate whether a service is operational.

A container can be:

- Running but unhealthy.
- Running and healthy.
- Starting.
- Stopped.
- Failed.

Container status and application availability are related but different measurements.

A process can remain alive while the application is unable to process requests.

### Health-check parameters

Docker health checks use:

| Parameter | Purpose |
|---|---|
| test | Health-check command |
| interval | Time between checks |
| timeout | Maximum check duration |
| retries | Consecutive failures before unhealthy |
| start_period | Initial startup allowance |

Health checks should measure meaningful service readiness.

For PostgreSQL, `pg_isready` checks whether the server accepts connections.

For the backend, the HTTP endpoint also verifies database connectivity.

For the frontend, the health check verifies HTTP availability.

### Failure scenarios

| Failure | Expected behavior |
|---|---|
| Database unavailable at startup | Backend waits for database health |
| Backend unavailable | Frontend returns a gateway error |
| Invalid task JSON | Backend returns HTTP 400 |
| Database query failure | Backend returns HTTP 503 |
| Frontend container restart | Database volume remains intact |
| Invalid Compose configuration | Validation fails before deployment |
| Database container recreation | Existing named volume is reused |

A restart policy does not guarantee application correctness. Monitoring, alerting, recovery procedures, and appropriate resource limits remain necessary.

## 13. Docker Deployment Workflow

### Project initialization

Run the Python project manager's `init` command from the directory where the project should be created.

It creates:

- `compose.yaml`
- `backend/Dockerfile`
- `backend/requirements.txt`
- `backend/main.py`
- `frontend/Dockerfile`
- `frontend/server.js`
- `database/init.sql`

The Python manager itself is the separately maintained `docker_project.py` file.

### Configuration

Create a `.env` file alongside `compose.yaml`.

Define a strong development database password:

`DB_PASSWORD=replace-with-a-strong-local-password`

Do not commit `.env` files containing credentials.

### Validate configuration

Run `python docker_project.py validate`.

This invokes Docker Compose configuration validation.

### Build and start

Run `python docker_project.py up`.

Docker Compose:

1. Builds the backend image.
2. Builds the frontend image.
3. Creates application networks.
4. Creates the database volume if necessary.
5. Starts PostgreSQL.
6. Waits for PostgreSQL health.
7. Starts the backend.
8. Waits for backend health.
9. Starts the frontend.

### Verify deployment

Open:

`http://localhost:3000`

Create a task and verify that it appears in the task list.

Check backend health:

`http://localhost:8000/health`

Expected health response:

`{"status": "healthy", "database": "connected"}`

### Inspect services

Run `python docker_project.py status`.

Run `python docker_project.py logs` to inspect application logs.

Individual services can be inspected using:

- `python docker_project.py logs --service frontend`
- `python docker_project.py logs --service backend`
- `python docker_project.py logs --service database`

### Stop the application

Run `python docker_project.py down`.

The containers are removed, but the named PostgreSQL volume is retained.

### Remove persistent data

Run `python docker_project.py clean --confirm`.

This removes containers and the project's named volume.

Database data cannot be recovered from that volume after deletion unless an independent backup exists.

## 14. PostgreSQL Operational Model

The advanced PostgreSQL implementation models a larger Docker deployment-management system.

It contains the following relational entities:

| Table | Responsibility |
|---|---|
| services | Application service definitions |
| service_dependencies | Service dependency relationships |
| networks | Docker network definitions |
| service_networks | Network membership |
| containers | Container instances |
| volumes | Storage definitions |
| container_volumes | Volume attachments |
| port_mappings | Host and container ports |
| health_checks | Health-check history |
| deployments | Deployment records |
| deployment_services | Per-service deployment state |
| deployment_events | Operational events |

### Referential integrity

Foreign keys ensure that dependent records reference existing services, containers, volumes, and deployments.

Unique constraints prevent duplicate service names and host port mappings.

Check constraints validate port ranges, service names, and storage mount paths.

### Triggers

The container creation trigger records container registration events.

The container transition trigger prevents invalid lifecycle changes.

The volume attachment trigger ensures that the modeled database storage uses a persistent volume.

### Functions

`dependencies_healthy()` checks whether required dependencies have healthy containers.

`database_storage_ready()` checks the persistent storage requirement.

`deployment_eligible()` evaluates whether a service satisfies the modeled deployment conditions.

### Views

`service_runtime_report` combines service definitions, containers, and the latest health-check information.

This simplifies operational reporting without duplicating the underlying records.

### Transactions

Deployment initialization and sample startup operations use transactions.

If an error occurs before commit, the transaction can be rolled back.

This prevents partially completed database changes from being treated as successful operations.

## 15. Security Considerations

### Secrets

The Compose configuration supports environment-based configuration for development.

A production environment should use managed secrets rather than committed passwords or unrestricted environment files.

Credentials should be rotated periodically.

### Container privileges

The frontend and backend run as non-root users.

The backend uses a read-only root filesystem and a temporary filesystem for writable temporary data.

The database has a separate service identity and is not published to the host.

### Network boundaries

The database is accessible through the internal Docker network.

Only necessary application ports are published.

The host bindings use loopback addresses for local development.

### Image security

Production images should use controlled, reviewed image versions.

Avoid relying on mutable tags for reproducible deployments.

Images should be scanned for known vulnerabilities.

Build dependencies should be minimized.

### Application security

The backend validates request sizes and task titles.

SQL queries use parameterized statements.

The frontend uses text-based DOM insertion for task titles rather than interpreting task data as HTML.

Production deployments should also implement authentication, authorization, HTTPS, request rate limits, and structured audit logging.

## 16. Performance Considerations

### Build performance

Docker layer caching reduces unnecessary dependency installation.

Small runtime images reduce transfer and storage costs.

### Application performance

The frontend uses asynchronous HTTP operations.

The backend uses a threaded HTTP server.

The database uses an index on task creation time.

A connection pool should be introduced when the application handles substantial concurrent traffic.

### Database performance

The task retrieval operation orders records by ID and limits the result set to 100 records.

This avoids returning the entire table for every request.

The more advanced SQL model indexes service status, dependency relationships, container status, deployment history, and health-check timestamps.

### Scaling

The frontend and backend can be replicated independently when the application architecture supports multiple instances.

The database requires a separate scaling strategy involving connection management, backups, replication, and consistency requirements.

Scaling the number of containers does not automatically scale the database's write capacity.

## 17. Project Structure

After initialization, the application directory contains:

- `docker_project.py`
- `compose.yaml`
- `.env`
- `backend/`
  - `Dockerfile`
  - `requirements.txt`
  - `main.py`
- `frontend/`
  - `Dockerfile`
  - `server.js`
- `database/`
  - `init.sql`

The C++ and Java programs are independent deployment-model demonstrations and can be compiled outside the application containers.

The PostgreSQL operational schema is an extended governance model. The runnable three-service application uses the smaller task-table schema in `database/init.sql`.

## 18. Running the Individual Implementations

### Python

Requires Python 3.10 or later.

The project manager uses standard-library modules.

Psycopg is installed inside the backend container through its requirements file.

### JavaScript

Requires Node.js 22 or later.

The frontend uses built-in Node.js modules and the native Fetch API.

### C++17

Compile using a C++17-compatible compiler.

The program uses only the C++ standard library.

### Java 17

Compile the Java implementation using Java 17.

The implementation does not require third-party libraries.

### PostgreSQL

The application uses PostgreSQL 17.

The extended database model uses PostgreSQL-specific features, including enums, PL/pgSQL functions, triggers, procedures, recursive CTEs, and lateral joins.

## 19. Technical Limitations

The project is designed as a local development and educational deployment environment.

It does not implement:

- Kubernetes orchestration.
- Production-grade secret management.
- Automated database backups.
- Database replication.
- Distributed tracing.
- Centralized log aggregation.
- Production authentication.
- Multi-host networking.
- Automatic schema migration.
- Distributed circuit-breaker state.
- Automatic rollback of failed application deployments.

The C++ and Java programs model deployment behavior rather than controlling actual Docker containers.

The Python manager invokes Docker Compose, while the JavaScript frontend and Python backend are executable application services.

The PostgreSQL extended governance model is separate from the minimal application schema used by the three-service Compose deployment.

These distinctions prevent a deployment simulation from being confused with actual container orchestration or production infrastructure management.
