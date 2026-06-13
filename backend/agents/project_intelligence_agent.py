"""
ManageAI Project Intelligence Agent

Lightweight, read-mostly machine agent for discovering local projects and
streaming runtime telemetry to the central Project Intelligence platform.
Control commands are intentionally gated behind --allow-control and project
level command allowlists.
"""

import argparse
import asyncio
import contextlib
import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlparse

try:
    import psutil
except Exception:
    psutil = None

try:
    import websockets
except Exception as exc:
    raise SystemExit("Install websockets first: pip install websockets") from exc


AGENT_VERSION = "1.0.0"
SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".next",
    ".nuxt",
    ".venv",
    "dist",
    "build",
    "node_modules",
    "target",
    "vendor",
    "__pycache__",
}
LOG_CANDIDATES = (
    "logs/app.log",
    "logs/error.log",
    "storage/logs/laravel.log",
    "npm-debug.log",
    "yarn-error.log",
)
DEFAULT_COMMAND_TIMEOUT = 900


@dataclass
class DiscoveredProject:
    root: Path
    external_id: str
    name: str
    framework: str
    language: str
    version: str = ""
    build_status: str = "unknown"
    deployment_status: str = "not_deployed"
    runtime_status: str = "unknown"
    port: int | None = None
    url: str = ""
    current_branch: str = ""
    last_commit_sha: str = ""
    last_commit_message: str = ""
    last_commit_author: str = ""
    last_commit_at: str | None = None
    repository_url: str = ""
    metadata: dict = field(default_factory=dict)

    def payload(self, environment: str, developer: str, machine_name: str) -> dict:
        return {
            "external_id": self.external_id,
            "name": self.name,
            "developer": developer,
            "machine_name": machine_name,
            "environment": environment,
            "framework": self.framework,
            "language": self.language,
            "root_path_hash": sha256_text(str(self.root)),
            "repository_url": self.repository_url,
            "runtime_status": self.runtime_status,
            "current_branch": self.current_branch,
            "last_commit_sha": self.last_commit_sha,
            "last_commit_message": self.last_commit_message,
            "last_commit_author": self.last_commit_author,
            "last_commit_at": self.last_commit_at,
            "build_status": self.build_status,
            "deployment_status": self.deployment_status,
            "version": self.version,
            "port": self.port,
            "url": self.url,
            "metadata": {
                **self.metadata,
                "root_name": self.root.name,
                "root_path_hash": sha256_text(str(self.root)),
            },
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()


def bounded_text(value: str, limit: int = 8000) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + "...[truncated]"


def run_capture(args: list[str], cwd: Path, timeout: int = 8) -> str:
    try:
        result = subprocess.run(
            args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            shell=False,
        )
    except Exception:
        return ""
    return (result.stdout or result.stderr or "").strip()


def normalize_server(server: str) -> str:
    value = (server or "ws://127.0.0.1:8001").strip().rstrip("/")
    if value.startswith("http://"):
        return f"ws://{value.removeprefix('http://')}"
    if value.startswith("https://"):
        return f"wss://{value.removeprefix('https://')}"
    return value


def default_machine_id() -> str:
    raw = f"{platform.node()}:{uuid.getnode()}:{platform.platform()}"
    return sha256_text(raw)[:32]


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}


def package_script(project: DiscoveredProject, script: str) -> list[str] | None:
    package = project.metadata.get("package_json") or {}
    scripts = package.get("scripts") or {}
    if script not in scripts:
        return None
    package_manager = "npm"
    if (project.root / "pnpm-lock.yaml").exists():
        package_manager = "pnpm"
    elif (project.root / "yarn.lock").exists():
        package_manager = "yarn"
    return [package_manager, "run", script]


class ProjectDiscoveryEngine:
    def __init__(self, roots: list[Path], max_depth: int):
        self.roots = [root.expanduser().resolve() for root in roots if root.exists()]
        self.max_depth = max(1, min(max_depth, 6))

    def discover(self) -> list[DiscoveredProject]:
        found: dict[str, DiscoveredProject] = {}
        for root in self.roots:
            for candidate in self.walk(root):
                project = self.detect(candidate)
                if project:
                    self.enrich_git(project)
                    found[project.external_id] = project
        return sorted(found.values(), key=lambda item: (item.framework, item.name.lower()))

    def walk(self, root: Path):
        queue: list[tuple[Path, int]] = [(root, 0)]
        seen: set[Path] = set()
        while queue:
            current, depth = queue.pop(0)
            if current in seen:
                continue
            seen.add(current)
            if self.has_marker(current):
                yield current
                continue
            if depth >= self.max_depth:
                continue
            try:
                children = list(current.iterdir())
            except (OSError, PermissionError):
                continue
            for child in children:
                if child.is_dir() and child.name not in SKIP_DIRS and not child.name.startswith("$"):
                    queue.append((child, depth + 1))

    def has_marker(self, path: Path) -> bool:
        marker_names = ("package.json", "manage.py", "artisan", "composer.json", "pom.xml", "build.gradle", "build.gradle.kts")
        return any((path / name).exists() for name in marker_names)

    def detect(self, root: Path) -> DiscoveredProject | None:
        if (root / "package.json").exists():
            return self.detect_node(root)
        if (root / "manage.py").exists():
            return self.make_project(root, "Django", "Python")
        if (root / "artisan").exists() or ((root / "composer.json").exists() and "laravel" in json.dumps(read_json(root / "composer.json")).lower()):
            return self.make_project(root, "Laravel", "PHP")
        if (root / "pom.xml").exists() or (root / "build.gradle").exists() or (root / "build.gradle.kts").exists():
            body = ""
            for name in ("pom.xml", "build.gradle", "build.gradle.kts"):
                with contextlib.suppress(Exception):
                    body += (root / name).read_text(encoding="utf-8", errors="ignore")[:20000].lower()
            if "spring-boot" in body or "org.springframework.boot" in body:
                return self.make_project(root, "Spring Boot", "Java")
        return None

    def detect_node(self, root: Path) -> DiscoveredProject:
        package = read_json(root / "package.json")
        deps = {**(package.get("dependencies") or {}), **(package.get("devDependencies") or {})}
        framework = "Node.js"
        if "next" in deps:
            framework = "Next.js"
        elif "react" in deps or "vite" in deps:
            framework = "React"
        language = "TypeScript" if (root / "tsconfig.json").exists() else "JavaScript"
        name = package.get("name") or root.name
        version = package.get("version") or ""
        project = self.make_project(root, framework, language, name=name, version=version)
        project.metadata["package_json"] = {"scripts": package.get("scripts") or {}, "private": bool(package.get("private"))}
        return project

    def make_project(self, root: Path, framework: str, language: str, *, name: str | None = None, version: str = "") -> DiscoveredProject:
        external_id = sha256_text(str(root).lower())[:24]
        return DiscoveredProject(
            root=root,
            external_id=external_id,
            name=name or root.name,
            framework=framework,
            language=language,
            version=version,
        )

    def enrich_git(self, project: DiscoveredProject) -> None:
        if not (project.root / ".git").exists():
            return
        project.current_branch = run_capture(["git", "rev-parse", "--abbrev-ref", "HEAD"], project.root)
        project.last_commit_sha = run_capture(["git", "rev-parse", "--short=12", "HEAD"], project.root)
        project.last_commit_message = run_capture(["git", "log", "-1", "--pretty=%s"], project.root)
        project.last_commit_author = run_capture(["git", "log", "-1", "--pretty=%an"], project.root)
        commit_at = run_capture(["git", "log", "-1", "--pretty=%cI"], project.root)
        project.last_commit_at = commit_at or None
        project.repository_url = run_capture(["git", "config", "--get", "remote.origin.url"], project.root)


class RuntimeSampler:
    def __init__(self):
        self._last_net = None
        self._last_net_ts = None

    def listening_processes(self) -> list[dict]:
        if not psutil:
            return []
        rows = []
        for proc in psutil.process_iter(["pid", "name", "cmdline", "cwd", "status", "cpu_percent", "memory_info"]):
            try:
                connections = proc.net_connections(kind="inet")
            except (psutil.AccessDenied, psutil.NoSuchProcess, AttributeError):
                continue
            ports = []
            for conn in connections:
                if getattr(conn, "status", "") == psutil.CONN_LISTEN and conn.laddr:
                    ports.append(conn.laddr.port)
            if not ports:
                continue
            try:
                info = proc.info
                rows.append({
                    "pid": info.get("pid"),
                    "name": info.get("name") or "",
                    "cmdline": " ".join(info.get("cmdline") or []),
                    "cwd": info.get("cwd") or "",
                    "status": info.get("status") or "",
                    "cpu_percent": float(info.get("cpu_percent") or 0),
                    "memory_mb": round((getattr(info.get("memory_info"), "rss", 0) or 0) / 1024 / 1024, 2),
                    "ports": sorted(set(ports)),
                })
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                continue
        return rows

    def enrich_projects(self, projects: list[DiscoveredProject]) -> None:
        processes = self.listening_processes()
        for project in projects:
            matched = [proc for proc in processes if self.matches_project(project.root, proc)]
            if not matched:
                project.runtime_status = "stopped"
                continue
            project.runtime_status = "running"
            first_port = matched[0]["ports"][0] if matched[0].get("ports") else None
            project.port = int(first_port) if first_port else None
            project.url = f"http://127.0.0.1:{project.port}" if project.port else ""
            project.metadata["processes"] = [
                {
                    "pid": proc["pid"],
                    "name": proc["name"],
                    "ports": proc["ports"],
                    "memory_mb": proc["memory_mb"],
                }
                for proc in matched[:8]
            ]

    def matches_project(self, root: Path, proc: dict) -> bool:
        root_text = str(root).lower()
        cwd = str(proc.get("cwd") or "").lower()
        cmdline = str(proc.get("cmdline") or "").lower()
        return cwd.startswith(root_text) or root_text in cmdline

    def metrics_for(self, projects: list[DiscoveredProject]) -> list[dict]:
        now = utc_now()
        net_rx, net_tx = self.network_rates()
        rows = []
        process_rows = self.listening_processes()
        for project in projects:
            matched = [proc for proc in process_rows if self.matches_project(project.root, proc)]
            cpu = sum(proc.get("cpu_percent") or 0 for proc in matched)
            memory_mb = sum(proc.get("memory_mb") or 0 for proc in matched)
            memory_percent = self.memory_percent(memory_mb)
            rows.append(
                {
                    "project_id": project.external_id,
                    "cpu_percent": round(cpu, 2),
                    "memory_percent": round(memory_percent, 2),
                    "memory_mb": round(memory_mb, 2),
                    "disk_percent": self.disk_percent(project.root),
                    "network_rx_bps": net_rx,
                    "network_tx_bps": net_tx,
                    "active_users": 0,
                    "requests_per_second": 0,
                    "error_rate_percent": 0,
                    "latency_ms": 0,
                    "process_count": len(matched),
                    "container_count": self.container_count(project),
                    "recorded_at": now,
                }
            )
        return rows

    def memory_percent(self, memory_mb: float) -> float:
        if not psutil:
            return 0
        total_mb = psutil.virtual_memory().total / 1024 / 1024
        return (memory_mb / total_mb) * 100 if total_mb else 0

    def disk_percent(self, root: Path) -> float:
        if not psutil:
            return 0
        try:
            return round(psutil.disk_usage(str(root.anchor or root)).percent, 2)
        except Exception:
            return 0

    def network_rates(self) -> tuple[int, int]:
        if not psutil:
            return 0, 0
        now = time.monotonic()
        current = psutil.net_io_counters()
        if not current:
            return 0, 0
        if self._last_net is None:
            self._last_net = current
            self._last_net_ts = now
            return 0, 0
        elapsed = max(now - (self._last_net_ts or now), 0.001)
        rx = int((current.bytes_recv - self._last_net.bytes_recv) / elapsed)
        tx = int((current.bytes_sent - self._last_net.bytes_sent) / elapsed)
        self._last_net = current
        self._last_net_ts = now
        return max(0, rx), max(0, tx)

    def container_count(self, project: DiscoveredProject) -> int:
        if not ((project.root / "docker-compose.yml").exists() or (project.root / "compose.yaml").exists() or (project.root / "Dockerfile").exists()):
            return 0
        return 1


class LogCollector:
    def collect(self, projects: list[DiscoveredProject], limit_per_project: int = 20) -> list[dict]:
        rows = []
        for project in projects:
            for relative in LOG_CANDIDATES:
                path = project.root / relative
                if not path.exists() or not path.is_file():
                    continue
                rows.extend(self.tail_file(project.external_id, path, limit_per_project))
        return rows[-500:]

    def tail_file(self, project_id: str, path: Path, limit: int) -> list[dict]:
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()[-limit:]
        except Exception:
            return []
        rows = []
        for line in lines:
            lower = line.lower()
            level = "info"
            if "critical" in lower or "fatal" in lower:
                level = "critical"
            elif "error" in lower or "exception" in lower or "traceback" in lower:
                level = "error"
            elif "warn" in lower or "failed" in lower:
                level = "warning"
            rows.append(
                {
                    "project_id": project_id,
                    "level": level,
                    "source": path.name,
                    "message": bounded_text(line, 2000),
                    "timestamp": utc_now(),
                }
            )
        return rows


class CommandExecutor:
    def __init__(self, allow_control: bool):
        self.allow_control = allow_control

    async def execute(self, command: dict, projects: dict[str, DiscoveredProject]) -> dict:
        command_type = command.get("command_type")
        project = projects.get(str(command.get("project_id") or ""))
        if command_type == "refresh_discovery":
            return {"success": True, "result": {"message": "Discovery refresh acknowledged."}}
        if command_type == "collect_logs":
            if not project:
                return {"success": False, "result": {"error": "Project not found on this machine."}}
            logs = LogCollector().collect([project], limit_per_project=80)
            return {"success": True, "result": {"logs": logs, "count": len(logs)}}
        if not self.allow_control:
            return {"success": False, "result": {"error": "Control commands require --allow-control on the agent."}}
        if not project:
            return {"success": False, "result": {"error": "Project not found on this machine."}}
        command_line = self.command_line(project, command_type, command.get("payload") or {})
        if not command_line:
            return {"success": False, "result": {"error": f"No safe command mapping exists for {command_type}."}}
        started = utc_now()
        proc = await asyncio.create_subprocess_exec(
            *command_line,
            cwd=str(project.root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            output, _ = await asyncio.wait_for(proc.communicate(), timeout=DEFAULT_COMMAND_TIMEOUT)
        except asyncio.TimeoutError:
            proc.kill()
            return {"success": False, "result": {"error": "Command timed out.", "started_at": started}}
        text = bounded_text(output.decode("utf-8", errors="replace") if output else "")
        return {
            "success": proc.returncode == 0,
            "result": {
                "command": command_line,
                "return_code": proc.returncode,
                "started_at": started,
                "completed_at": utc_now(),
                "output": text,
            },
        }

    def command_line(self, project: DiscoveredProject, command_type: str, payload: dict) -> list[str] | None:
        configured = self.configured_commands(project).get(command_type)
        if configured:
            return configured
        if command_type == "build":
            if project.framework in {"React", "Next.js", "Node.js"}:
                return package_script(project, "build")
            if project.framework == "Django":
                return [sys.executable, "manage.py", "check"]
            if project.framework == "Laravel":
                return ["php", "artisan", "test"]
            if project.framework == "Spring Boot":
                return ["mvn", "test"]
        if command_type in {"deploy", "rollback", "restart"}:
            return None
        return None

    def configured_commands(self, project: DiscoveredProject) -> dict[str, list[str]]:
        config_path = project.root / "manageai-agent.json"
        data = read_json(config_path)
        commands = data.get("commands") if isinstance(data, dict) else {}
        safe = {}
        for key, value in (commands or {}).items():
            if key in {"build", "deploy", "rollback", "restart"} and isinstance(value, list) and value:
                safe[key] = [str(part) for part in value]
        return safe


class ProjectIntelligenceAgent:
    def __init__(self, args):
        self.server = normalize_server(args.server)
        self.token = args.token
        self.environment = args.environment
        self.machine_id = args.machine_id or default_machine_id()
        self.machine_name = args.machine_name or socket.gethostname()
        self.developer = args.developer or os.getenv("USERNAME") or os.getenv("USER") or ""
        self.interval = max(5, args.interval)
        self.roots = [Path(root) for root in args.roots]
        self.max_depth = args.max_depth
        self.discovery = ProjectDiscoveryEngine(self.roots, self.max_depth)
        self.sampler = RuntimeSampler()
        self.logs = LogCollector()
        self.executor = CommandExecutor(args.allow_control)
        self.projects: dict[str, DiscoveredProject] = {}

    @property
    def url(self) -> str:
        return f"{self.server}/ws/project-agent/?token={quote(self.token)}"

    async def run(self) -> None:
        backoff = 1
        while True:
            try:
                async with websockets.connect(
                    self.url,
                    open_timeout=30,
                    ping_interval=20,
                    ping_timeout=60,
                    max_size=16 * 1024 * 1024,
                ) as ws:
                    print(f"Connected to {self.url}")
                    backoff = 1
                    await self.send_snapshot(ws)
                    consumer = asyncio.create_task(self.consume(ws))
                    producer = asyncio.create_task(self.produce(ws))
                    done, pending = await asyncio.wait({consumer, producer}, return_when=asyncio.FIRST_EXCEPTION)
                    for task in pending:
                        task.cancel()
                    for task in done:
                        task.result()
            except Exception as exc:
                wait = min(backoff, 60)
                print(f"Disconnected: {exc}. Reconnecting in {wait}s.")
                await asyncio.sleep(wait)
                backoff = min(backoff * 2, 60)

    async def produce(self, ws) -> None:
        while True:
            await asyncio.sleep(self.interval)
            await self.send_snapshot(ws)

    async def consume(self, ws) -> None:
        async for raw in ws:
            if isinstance(raw, bytes):
                continue
            message = json.loads(raw)
            for command in message.get("commands") or []:
                result = await self.executor.execute(command, self.projects)
                await ws.send(
                    json.dumps(
                        {
                            "type": "command.result",
                            "command_id": command.get("id"),
                            "success": result["success"],
                            "result": result["result"],
                        },
                        separators=(",", ":"),
                    )
                )

    async def send_snapshot(self, ws) -> None:
        projects = await asyncio.to_thread(self.discovery.discover)
        await asyncio.to_thread(self.sampler.enrich_projects, projects)
        self.projects = {project.external_id: project for project in projects}
        payload = {
            "type": "snapshot",
            "payload": {
                "heartbeat": self.heartbeat(),
                "projects": [project.payload(self.environment, self.developer, self.machine_name) for project in projects],
                "metrics": self.sampler.metrics_for(projects),
                "logs": self.logs.collect(projects),
            },
        }
        await ws.send(json.dumps(payload, separators=(",", ":")))

    def heartbeat(self) -> dict:
        return {
            "name": self.machine_name,
            "machine_id": self.machine_id,
            "hostname": socket.gethostname(),
            "os_name": platform.platform(),
            "version": AGENT_VERSION,
            "environment": self.environment,
            "capabilities": {
                "project_discovery": True,
                "runtime_metrics": bool(psutil),
                "git_monitoring": True,
                "log_capture": True,
                "command_control": self.executor.allow_control,
                "frameworks": ["React", "Next.js", "Django", "Node.js", "Laravel", "Spring Boot"],
            },
            "metadata": {
                "python": sys.version.split()[0],
                "scan_roots": [sha256_text(str(root)) for root in self.roots],
                "psutil": bool(psutil),
                "agent_started_at": utc_now(),
                "server_host": urlparse(self.server).hostname,
            },
        }


def default_roots() -> list[str]:
    cwd = str(Path.cwd())
    home = Path.home()
    candidates = [cwd, str(home / "Projects"), str(home / "projects"), str(home / "Desktop"), str(home / "Documents")]
    return list(dict.fromkeys(path for path in candidates if Path(path).exists()))


def main() -> None:
    parser = argparse.ArgumentParser(description="ManageAI Project Intelligence Agent")
    parser.add_argument("--server", default="ws://127.0.0.1:8001", help="ManageAI WebSocket server, for example ws://127.0.0.1:8001")
    parser.add_argument("--token", required=True, help="One-time agent token created from the Project Intelligence dashboard")
    parser.add_argument("--roots", nargs="+", default=default_roots(), help="Directories to scan for projects")
    parser.add_argument("--environment", default="development", choices=["localhost", "development", "qa", "staging", "production"], help="Environment label for discovered projects")
    parser.add_argument("--machine-id", default="", help="Stable machine identifier. Defaults to a hashed hardware/host fingerprint.")
    parser.add_argument("--machine-name", default="", help="Display name shown in the command center")
    parser.add_argument("--developer", default="", help="Developer or team owner shown for discovered projects")
    parser.add_argument("--interval", type=int, default=15, help="Heartbeat and telemetry interval in seconds")
    parser.add_argument("--max-depth", type=int, default=3, help="Project discovery depth per scan root")
    parser.add_argument("--allow-control", action="store_true", help="Allow safe build/deploy/restart/rollback command execution")
    args = parser.parse_args()

    print("ManageAI Project Intelligence Agent")
    print(f"Server      : {normalize_server(args.server)}")
    print(f"Machine     : {args.machine_name or socket.gethostname()}")
    print(f"Environment : {args.environment}")
    print(f"Roots       : {', '.join(args.roots)}")
    print(f"Control     : {'enabled' if args.allow_control else 'observe-only'}")
    asyncio.run(ProjectIntelligenceAgent(args).run())


if __name__ == "__main__":
    main()
