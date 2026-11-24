#!/usr/bin/env python3
"""
Docker Multi-Service Project Manager

Manages a containerized application containing:
- JavaScript frontend
- Python REST backend
- PostgreSQL database
- Docker bridge network
- Persistent database volume
- Health checks and service dependencies

Requirements:
    Python 3.10+
    Docker Engine
    Docker Compose v2

Usage:
    python docker_project.py init
    python docker_project.py validate
    python docker_project.py up
    python docker_project.py status
    python docker_project.py logs
    python docker_project.py down
    python docker_project.py clean
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


PROJECT_NAME = "docker-multiservice"
ROOT = Path(__file__).resolve().parent


class ProjectError(Exception):
    """Raised when project operations fail."""


class ServiceState(str, Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Service:
    name: str
    container_port: int
    health_endpoint: str | None = None
    persistent: bool = False


SERVICES = (
    Service("frontend", 3000, "/"),
    Service("backend", 8000, "/health"),
    Service("database", 5432, persistent=True),
)


class CommandRunner:
    """Executes external commands without shell interpolation."""

    @staticmethod
    def run(
        command: list[str],
        check: bool = True,
        capture: bool = False,
    ) -> subprocess.CompletedProcess[str]:

        try:
            result = subprocess.run(
                command,
                check=False,
                text=True,
                capture_output=capture,
                timeout=300,
            )
        except FileNotFoundError as exc:
            raise ProjectError(
                f"Required executable not found: {command[0]}"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise ProjectError(
                f"Command timed out: {' '.join(command)}"
            ) from exc

        if check and result.returncode != 0:
            raise ProjectError(
                result.stderr.strip()
                or f"Command failed with exit code {result.returncode}"
            )

        return result


class DockerProject:
    """Controls the complete multi-container application."""

    def __init__(self, root: Path = ROOT):
        self.root = root
        self.compose_file = root / "compose.yaml"

    def docker_available(self) -> bool:
        result = CommandRunner.run(
            ["docker", "version"],
            check=False,
            capture=True,
        )
        return result.returncode == 0

    def compose_available(self) -> bool:
        result = CommandRunner.run(
            ["docker", "compose", "version"],
            check=False,
            capture=True,
        )
        return result.returncode == 0

    def verify_environment(self) -> None:
        if not self.docker_available():
            raise ProjectError(
                "Docker is unavailable. Start Docker Desktop or Docker Engine."
            )

        if not self.compose_available():
            raise ProjectError(
                "Docker Compose v2 is required."
            )

    @staticmethod
    def project_files() -> dict[str, str]:

        return {
            "compose.yaml": r"""
name: docker-multiservice

services:
  database:
    image: postgres:17-alpine
    container_name: docker-database
    restart: unless-stopped
    environment:
      POSTGRES_DB: appdb
      POSTGRES_USER: appuser
      POSTGRES_PASSWORD: ${DB_PASSWORD:-local-development-password}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./database/init.sql:/docker-entrypoint-initdb.d/01-init.sql:ro
    networks:
      - internal
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U appuser -d appdb"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s
    security_opt:
      - no-new-privileges:true

  backend:
    build:
      context: ./backend
    container_name: docker-backend
    restart: unless-stopped
    environment:
      DB_HOST: database
      DB_PORT: 5432
      DB_NAME: appdb
      DB_USER: appuser
      DB_PASSWORD: ${DB_PASSWORD:-local-development-password}
      APP_PORT: 8000
    depends_on:
      database:
        condition: service_healthy
    networks:
      - internal
      - public
    ports:
      - "127.0.0.1:8000:8000"
    healthcheck:
      test:
        - CMD
        - python
        - -c
        - "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)"
      interval: 15s
      timeout: 5s
      retries: 3
      start_period: 15s
    read_only: true
    tmpfs:
      - /tmp
    security_opt:
      - no-new-privileges:true

  frontend:
    build:
      context: ./frontend
    container_name: docker-frontend
    restart: unless-stopped
    environment:
      BACKEND_URL: http://backend:8000
      PORT: 3000
    depends_on:
      backend:
        condition: service_healthy
    networks:
      - public
      - internal
    ports:
      - "127.0.0.1:3000:3000"
    healthcheck:
      test:
        - CMD
        - node
        - -e
        - "fetch('http://localhost:3000/').then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"
      interval: 15s
      timeout: 5s
      retries: 3
    security_opt:
      - no-new-privileges:true

networks:
  public:
    driver: bridge
  internal:
    driver: bridge

volumes:
  postgres_data:
    driver: local
""",
            "backend/Dockerfile": r"""
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN useradd --system --uid 10001 appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

USER appuser

EXPOSE 8000

CMD ["python", "main.py"]
""",
            "backend/requirements.txt": "psycopg[binary]==3.2.9\n",
            "backend/main.py": r"""
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import psycopg
from psycopg.rows import dict_row


def database_connection():
    return psycopg.connect(
        host=os.environ.get("DB_HOST", "database"),
        port=int(os.environ.get("DB_PORT", "5432")),
        dbname=os.environ.get("DB_NAME", "appdb"),
        user=os.environ.get("DB_USER", "appuser"),
        password=os.environ["DB_PASSWORD"],
        connect_timeout=3,
        row_factory=dict_row,
    )


def initialize_database():
    # Compose health checks control startup order.
    # Retries also handle temporary database unavailability.
    for attempt in range(10):
        try:
            with database_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS tasks (
                            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                            title VARCHAR(200) NOT NULL,
                            completed BOOLEAN NOT NULL DEFAULT FALSE,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        )
                    """)
            return
        except psycopg.Error:
            if attempt == 9:
                raise
            time.sleep(min(2 ** attempt, 10))


class Handler(BaseHTTPRequestHandler):

    def send_json(self, status, payload):
        body = json.dumps(payload, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/health":
            try:
                with database_connection() as connection:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT 1")
                self.send_json(200, {
                    "status": "healthy",
                    "database": "connected"
                })
            except psycopg.Error:
                self.send_json(503, {
                    "status": "unhealthy",
                    "database": "unavailable"
                })
            return

        if path == "/api/tasks":
            try:
                with database_connection() as connection:
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            SELECT id, title, completed, created_at
                            FROM tasks
                            ORDER BY id DESC
                            LIMIT 100
                        """)
                        tasks = cursor.fetchall()

                self.send_json(200, {"tasks": tasks})
            except psycopg.Error:
                self.send_json(503, {"error": "Database unavailable"})
            return

        self.send_json(404, {"error": "Not found"})

    def do_POST(self):
        if urlparse(self.path).path != "/api/tasks":
            self.send_json(404, {"error": "Not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 4096:
                self.send_json(400, {"error": "Invalid request size"})
                return

            payload = json.loads(self.rfile.read(length))
            title = payload.get("title")

            if not isinstance(title, str):
                self.send_json(400, {"error": "Title must be text"})
                return

            title = title.strip()

            if not title or len(title) > 200:
                self.send_json(400, {"error": "Title must contain 1-200 characters"})
                return

            with database_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO tasks (title)
                        VALUES (%s)
                        RETURNING id, title, completed, created_at
                        """,
                        (title,)
                    )
                    task = cursor.fetchone()

            self.send_json(201, {"task": task})

        except (json.JSONDecodeError, UnicodeDecodeError):
            self.send_json(400, {"error": "Invalid JSON"})
        except psycopg.Error:
            self.send_json(503, {"error": "Database unavailable"})

    def log_message(self, format, *args):
        print(format % args)


if __name__ == "__main__":
    initialize_database()

    port = int(os.environ.get("APP_PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)

    print(f"Backend listening on port {port}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
""",
            "frontend/Dockerfile": r"""
FROM node:22-alpine

WORKDIR /app

COPY server.js .

ENV NODE_ENV=production
ENV PORT=3000

USER node

EXPOSE 3000

CMD ["node", "server.js"]
""",
            "frontend/server.js": r"""
const http = require("node:http");

const PORT = Number(process.env.PORT || 3000);
const BACKEND_URL = process.env.BACKEND_URL || "http://backend:8000";

const page = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Container Task Manager</title>
<style>
body{font-family:Arial,sans-serif;max-width:760px;margin:60px auto;padding:20px;background:#f4f6fa;color:#172033}
main{background:white;padding:28px;border-radius:12px}
input,button{padding:12px;margin:5px;border:1px solid #ccc;border-radius:6px}
button{background:#183b68;color:white;cursor:pointer}
li{padding:10px;border-bottom:1px solid #ddd}
#status{margin:15px 0}
</style>
</head>
<body>
<main>
<h1>Container Task Manager</h1>
<p>Frontend → Backend → PostgreSQL</p>
<div id="status">Checking services...</div>
<form id="taskForm">
<input id="title" maxlength="200" required placeholder="Enter a task">
<button type="submit">Add task</button>
</form>
<ul id="tasks"></ul>
</main>
<script>
const status = document.getElementById("status");
const list = document.getElementById("tasks");

async function loadTasks() {
    try {
        const response = await fetch("/api/tasks");
        if (!response.ok) throw new Error("Backend unavailable");

        const data = await response.json();
        list.replaceChildren();

        for (const task of data.tasks) {
            const item = document.createElement("li");
            item.textContent =
                task.title + (task.completed ? " (Completed)" : "");
            list.appendChild(item);
        }

        status.textContent = "Application connected";
    } catch (error) {
        status.textContent = error.message;
    }
}

document.getElementById("taskForm").addEventListener("submit", async event => {
    event.preventDefault();

    const title = document.getElementById("title").value.trim();
    if (!title) return;

    try {
        const response = await fetch("/api/tasks", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({title})
        });

        if (!response.ok) throw new Error("Task creation failed");

        document.getElementById("title").value = "";
        await loadTasks();
    } catch (error) {
        status.textContent = error.message;
    }
});

loadTasks();
</script>
</body>
</html>`;

const server = http.createServer(async (req, res) => {
    const path = new URL(req.url, "http://localhost").pathname;

    if (path === "/") {
        res.writeHead(200, {
            "Content-Type": "text/html; charset=utf-8",
            "Content-Length": Buffer.byteLength(page),
            "X-Content-Type-Options": "nosniff"
        });
        return res.end(page);
    }

    if (path === "/api/tasks" && ["GET", "POST"].includes(req.method)) {
        try {
            const chunks = [];
            for await (const chunk of req) {
                chunks.push(chunk);
                if (Buffer.concat(chunks).length > 4096) {
                    res.writeHead(413);
                    return res.end();
                }
            }

            const response = await fetch(
                BACKEND_URL + "/api/tasks",
                {
                    method: req.method,
                    headers: req.method === "POST"
                        ? {"Content-Type": req.headers["content-type"] || "application/json"}
                        : {},
                    body: req.method === "POST"
                        ? Buffer.concat(chunks)
                        : undefined,
                    signal: AbortSignal.timeout(5000)
                }
            );

            const body = await response.text();
            res.writeHead(response.status, {
                "Content-Type": "application/json",
                "Cache-Control": "no-store"
            });
            return res.end(body);
        } catch (error) {
            res.writeHead(503, {"Content-Type": "application/json"});
            return res.end(JSON.stringify({
                error: "Backend unavailable"
            }));
        }
    }

    res.writeHead(404, {"Content-Type": "application/json"});
    res.end(JSON.stringify({error: "Not found"}));
});

server.listen(PORT, "0.0.0.0", () => {
    console.log(`Frontend listening on ${PORT}`);
});

function shutdown() {
    server.close(() => process.exit(0));
    setTimeout(() => process.exit(1), 5000).unref();
}

process.on("SIGTERM", shutdown);
process.on("SIGINT", shutdown);
""",
            "database/init.sql": r"""
CREATE TABLE IF NOT EXISTS tasks (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    completed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT task_title_not_empty CHECK (length(trim(title)) > 0)
);

CREATE INDEX IF NOT EXISTS idx_tasks_created_at
ON tasks (created_at DESC);
""",
        }

    def initialize(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

        for relative_path, content in self.project_files().items():
            target = self.root / relative_path

            if target.exists():
                raise ProjectError(
                    f"Refusing to overwrite existing file: {target}"
                )

            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content.lstrip(), encoding="utf-8")

            print(f"Created: {relative_path}")

        print("\nProject files created successfully.")
        print("Review .env configuration before deployment.")

    def compose(self, *arguments: str) -> None:
        self.verify_environment()

        if not self.compose_file.exists():
            raise ProjectError(
                "compose.yaml not found. Run the init command first."
            )

        CommandRunner.run(
            [
                "docker",
                "compose",
                "-f",
                str(self.compose_file),
                *arguments,
            ]
        )

    def validate(self) -> None:
        self.verify_environment()

        if not self.compose_file.exists():
            raise ProjectError("compose.yaml does not exist.")

        self.compose("config", "--quiet")
        print("Docker Compose configuration is valid.")

    def up(self) -> None:
        self.validate()
        print("Building and starting services...")
        self.compose("up", "--build", "-d")
        self.wait_for_backend()

    def wait_for_backend(self, timeout: int = 90) -> None:
        deadline = time.monotonic() + timeout
        url = "http://127.0.0.1:8000/health"

        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(url, timeout=3) as response:
                    data = json.loads(response.read())

                    if response.status == 200:
                        print("Backend health check passed:", data)
                        return

            except (
                urllib.error.URLError,
                TimeoutError,
                json.JSONDecodeError,
            ):
                time.sleep(2)

        raise ProjectError(
            "Backend did not become healthy within the timeout."
        )

    def status(self) -> None:
        self.compose("ps")

    def logs(self, service: str | None = None) -> None:
        arguments = ["logs", "--tail", "100"]
        if service:
            arguments.append(service)
        self.compose(*arguments)

    def down(self, remove_volumes: bool = False) -> None:
        arguments = ["down"]
        if remove_volumes:
            arguments.append("--volumes")
        self.compose(*arguments)

    def clean(self, confirm: bool) -> None:
        if not confirm:
            raise ProjectError(
                "Use --confirm to remove containers and persistent database data."
            )

        self.down(remove_volumes=True)
        print("Containers and project volumes removed.")

    def inspect_health(self) -> dict[str, Any]:
        result = CommandRunner.run(
            ["docker", "compose", "ps", "--format", "json"],
            capture=True,
        )

        try:
            return {
                "containers": json.loads(result.stdout)
                if result.stdout.strip().startswith("[")
                else result.stdout
            }
        except json.JSONDecodeError:
            return {"output": result.stdout}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Docker multi-service project manager"
    )

    parser.add_argument(
        "command",
        choices=[
            "init",
            "validate",
            "up",
            "status",
            "logs",
            "down",
            "clean",
            "inspect",
        ],
    )

    parser.add_argument("--service", help="Specific service for logs")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirm destructive volume deletion",
    )

    args = parser.parse_args()
    project = DockerProject()

    try:
        if args.command == "init":
            project.initialize()
        elif args.command == "validate":
            project.validate()
        elif args.command == "up":
            project.up()
        elif args.command == "status":
            project.status()
        elif args.command == "logs":
            project.logs(args.service)
        elif args.command == "down":
            project.down()
        elif args.command == "clean":
            project.clean(args.confirm)
        elif args.command == "inspect":
            project.verify_environment()
            print(json.dumps(project.inspect_health(), indent=2))

        return 0

    except ProjectError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nOperation interrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
