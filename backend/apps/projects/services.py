import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import serializers

from apps.deployments.models import DeploymentControl
from apps.notifications.services import notify_user


GITHUB_REPO_RE = re.compile(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/#?]+)", re.IGNORECASE)
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


class GitHubAPIError(Exception):
    pass


def parse_github_repo_url(url):
    match = GITHUB_REPO_RE.search(url or "")
    if not match:
        raise serializers.ValidationError("Repository URL must be a GitHub repository URL.")
    owner = match.group("owner")
    repo = match.group("repo").removesuffix(".git")
    return owner, repo


def validate_local_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise serializers.ValidationError("Local URL must use http or https.")
    hostname = parsed.hostname or ""
    if hostname not in LOCAL_HOSTS and not hostname.endswith(".localhost"):
        raise serializers.ValidationError("Local connections must point to localhost or 127.0.0.1.")
    return True


def parse_github_datetime(value):
    if not value:
        return None
    parsed = parse_datetime(value)
    if parsed:
        return parsed if timezone.is_aware(parsed) else timezone.make_aware(parsed)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if timezone.is_aware(parsed) else timezone.make_aware(parsed)
    except ValueError:
        return None


class GitHubClient:
    api_root = "https://api.github.com"

    def __init__(self, token=None):
        self.token = token or getattr(settings, "GITHUB_TOKEN", "")

    def request(self, path):
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "ManageAI/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request(f"{self.api_root}{path}", headers=headers)
        try:
            with urlopen(request, timeout=12) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            message = exc.read().decode("utf-8", errors="ignore") or exc.reason
            raise GitHubAPIError(f"GitHub API returned {exc.code}: {message}") from exc
        except URLError as exc:
            raise GitHubAPIError(f"GitHub API is not reachable: {exc.reason}") from exc

    def repo(self, owner, repo):
        return self.request(f"/repos/{owner}/{repo}")

    def branches(self, owner, repo):
        payload = self.request(f"/repos/{owner}/{repo}/branches?per_page=100")
        return [{"name": item["name"], "sha": item.get("commit", {}).get("sha", "")} for item in payload]

    def commits(self, owner, repo, branch, limit=25):
        payload = self.request(f"/repos/{owner}/{repo}/commits?sha={branch}&per_page={limit}")
        commits = []
        for item in payload:
            commit = item.get("commit", {})
            author = commit.get("author") or {}
            github_author = item.get("author") or {}
            commits.append(
                {
                    "sha": item.get("sha", ""),
                    "message": (commit.get("message") or "").splitlines()[0][:500],
                    "author_name": author.get("name", ""),
                    "author_email": author.get("email", ""),
                    "author_login": github_author.get("login", ""),
                    "committed_at": parse_github_datetime(author.get("date")),
                    "html_url": item.get("html_url", ""),
                    "branch": branch,
                }
            )
        return commits


def sync_project_commits(project, branch=None, limit=25):
    from .models import Project, ProjectCommit

    if project.connection_type != Project.ConnectionType.GITHUB:
        raise serializers.ValidationError("Project is not connected to GitHub.")
    if not project.github_owner or not project.github_repo:
        raise serializers.ValidationError("GitHub owner and repository are required before sync.")

    branch = branch or project.selected_branch or project.github_default_branch or "main"
    project.connection_status = Project.ConnectionStatus.SYNCING
    project.connection_status_message = f"Syncing {branch}"
    project.save(update_fields=["connection_status", "connection_status_message", "updated_at"])

    client = GitHubClient()
    try:
        repo_payload = client.repo(project.github_owner, project.github_repo)
        commits = client.commits(project.github_owner, project.github_repo, branch, limit=limit)
    except GitHubAPIError as exc:
        project.connection_status = Project.ConnectionStatus.ERROR
        project.connection_status_message = str(exc)[:500]
        project.save(update_fields=["connection_status", "connection_status_message", "updated_at"])
        raise

    saved = []
    for item in commits:
        commit, _ = ProjectCommit.objects.update_or_create(
            project=project,
            sha=item["sha"],
            branch=branch,
            defaults={
                "message": item["message"],
                "author_name": item["author_name"],
                "author_email": item["author_email"],
                "author_login": item["author_login"],
                "committed_at": item["committed_at"],
                "html_url": item["html_url"],
            },
        )
        saved.append(commit)

    latest = saved[0] if saved else None
    project.connection_status = Project.ConnectionStatus.CONNECTED
    project.connection_status_message = f"Synced {len(saved)} commits from {branch}"
    project.selected_branch = branch
    project.github_default_branch = repo_payload.get("default_branch") or project.github_default_branch or branch
    project.last_synced_at = timezone.now()
    if latest:
        project.last_commit_sha = latest.sha
        project.last_commit_message = latest.message[:280]
        project.last_commit_author = latest.author_login or latest.author_name
        project.last_commit_at = latest.committed_at
    project.save(
        update_fields=[
            "connection_status",
            "connection_status_message",
            "selected_branch",
            "github_default_branch",
            "last_synced_at",
            "last_commit_sha",
            "last_commit_message",
            "last_commit_author",
            "last_commit_at",
            "updated_at",
        ]
    )
    broadcast_project_update(project, "project.commits.synced")
    return saved


def deploy_project_from_branch(project, user, branch=None, environment=None, notes=""):
    from .models import Project

    branch = branch or project.selected_branch or project.github_default_branch or "main"
    latest = project.commits.filter(branch=branch).first()
    if project.connection_type == Project.ConnectionType.GITHUB and not latest:
        try:
            commits = sync_project_commits(project, branch=branch, limit=10)
            latest = commits[0] if commits else None
        except GitHubAPIError:
            latest = None

    deployment, _ = DeploymentControl.objects.get_or_create(project=project, defaults={"environment": environment or "production"})
    if environment:
        deployment.environment = environment
    deployment.source_branch = branch if project.connection_type == Project.ConnectionType.GITHUB else ""
    deployment.commit_sha = latest.sha if latest else ""
    deployment.version = latest.sha[:7] if latest else (project.selected_branch or "manual")
    deployment.notes = notes or f"Deployment triggered from {branch}"
    deployment.set_enabled(True, user)

    project.connection_status = Project.ConnectionStatus.CONNECTED
    project.connection_status_message = f"Deployment healthy in {deployment.get_environment_display()}"
    project.selected_branch = branch if project.connection_type == Project.ConnectionType.GITHUB else project.selected_branch
    if project.status in {Project.Status.PLANNING, Project.Status.ON_HOLD}:
        project.status = Project.Status.ACTIVE
    project.save(update_fields=["connection_status", "connection_status_message", "selected_branch", "status", "updated_at"])

    recipients = {project.owner, project.created_by, project.client, *project.admins.all(), *project.developers.all()}
    for recipient in recipients:
        if recipient and recipient.id != user.id:
            notify_user(
                recipient=recipient,
                sender=user,
                title="Deployment updated",
                message=f"{project.name} deployed from {branch} to {deployment.get_environment_display()}.",
                type="SUCCESS",
                project=project,
            )
    broadcast_project_update(project, "project.deployment.updated")
    return deployment


def run_git_command(repo_path, args, timeout=90):
    process = subprocess.run(
        ["git", *args],
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if process.returncode:
        message = (process.stderr or process.stdout or "Git command failed.").strip()
        raise GitHubAPIError(message[:500])
    return process.stdout.strip()


def push_project_to_git(project, user, branch=None, commit_message=""):
    from .models import ProjectCommit

    if not project.local_repository_path:
        raise serializers.ValidationError({"local_repository_path": "Set a local repository path before pushing work."})

    repo_path = Path(project.local_repository_path).expanduser().resolve()
    if not repo_path.exists() or not (repo_path / ".git").exists():
        raise serializers.ValidationError({"local_repository_path": "The configured path is not a Git repository."})

    current_branch = run_git_command(repo_path, ["rev-parse", "--abbrev-ref", "HEAD"]) or "main"
    branch = branch or project.selected_branch or current_branch
    status_output = run_git_command(repo_path, ["status", "--porcelain"])
    if status_output:
        run_git_command(repo_path, ["add", "-A"])
        message = commit_message or f"{project.name}: developer update"
        run_git_command(repo_path, ["commit", "-m", message])

    run_git_command(repo_path, ["push", "origin", f"HEAD:{branch}"], timeout=180)
    sha = run_git_command(repo_path, ["rev-parse", "HEAD"])
    message = run_git_command(repo_path, ["show", "-s", "--format=%s", sha])
    author_name = run_git_command(repo_path, ["show", "-s", "--format=%an", sha])
    author_email = run_git_command(repo_path, ["show", "-s", "--format=%ae", sha])
    committed_at = parse_github_datetime(run_git_command(repo_path, ["show", "-s", "--format=%cI", sha]))

    commit, _ = ProjectCommit.objects.update_or_create(
        project=project,
        sha=sha,
        branch=branch,
        defaults={
            "message": message[:500],
            "author_name": author_name[:180],
            "author_email": author_email,
            "author_login": user.username or "",
            "committed_at": committed_at,
            "html_url": "",
        },
    )
    project.connection_type = project.ConnectionType.GITHUB
    project.connection_status = project.ConnectionStatus.CONNECTED
    project.connection_status_message = f"Pushed {sha[:7]} to {branch}"
    project.selected_branch = branch
    project.last_synced_at = timezone.now()
    project.last_commit_sha = sha
    project.last_commit_message = message[:280]
    project.last_commit_author = user.get_full_name() or user.email
    project.last_commit_at = committed_at
    project.save(
        update_fields=[
            "connection_type",
            "connection_status",
            "connection_status_message",
            "selected_branch",
            "last_synced_at",
            "last_commit_sha",
            "last_commit_message",
            "last_commit_author",
            "last_commit_at",
            "updated_at",
        ]
    )

    User = get_user_model()
    recipients = {project.owner, project.created_by, project.client, *project.admins.all(), *project.developers.all(), *User.objects.filter(role=User.Role.SUPER_ADMIN)}
    for recipient in recipients:
        if recipient and recipient.id != user.id:
            notify_user(
                recipient=recipient,
                sender=user,
                title="Git push completed",
                message=f"{project.name} was pushed to {branch} at {sha[:7]}.",
                type="SUCCESS",
                project=project,
            )
    broadcast_project_update(project, "project.git.pushed")
    return commit


def check_local_connection(project):
    validate_local_url(project.local_url)
    request = Request(project.local_url, method="HEAD", headers={"User-Agent": "ManageAI/1.0"})
    try:
        with urlopen(request, timeout=5) as response:
            return {"ok": True, "status_code": response.status, "reason": response.reason}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def normalize_text_list(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in re.split(r"[\n,;]+", value) if item.strip()]
    return []


def build_project_flow(project, prompt_text=""):
    """Build a deterministic delivery flow from project prompt fields."""
    technologies = normalize_text_list(project.technologies_used)
    features = normalize_text_list(project.features_to_implement)
    source_text = " ".join([prompt_text, project.project_idea, project.description, " ".join(features)]).lower()

    module_keywords = [
        ("Core Platform", ["auth", "rbac", "tenant", "user", "permission", "sso", "mfa"]),
        ("ITSM Service Desk", ["ticket", "sla", "incident", "request", "workflow", "approval"]),
        ("ITOM Monitoring", ["monitor", "device", "metric", "alert", "topology", "cloud"]),
        ("Security Operations", ["siem", "ueba", "soar", "threat", "mitre", "log"]),
        ("AI Operations", ["ai", "llm", "prediction", "anomaly", "assistant", "openai"]),
        ("Realtime Experience", ["websocket", "channels", "notification", "real-time", "realtime"]),
        ("Deployment", ["docker", "nginx", "celery", "redis", "postgres", "production"]),
    ]
    detected_modules = [name for name, words in module_keywords if any(word in source_text for word in words)]
    if not detected_modules:
        detected_modules = ["Core Platform", "Project Delivery", "Quality & Release"]

    feature_chunks = features[:8] or [project.name, "Role based dashboard", "Task workflow", "Release readiness"]
    flow = [
        {
            "key": "discover",
            "title": "Discovery & Scope",
            "phase": 1,
            "status": "READY",
            "owner_role": "Admin",
            "outcome": "Convert the prompt into approved scope, modules, data rules, and acceptance criteria.",
            "activities": [
                "Confirm business goal and target users",
                "Map modules to the delivery backlog",
                "Define access, audit, and approval boundaries",
            ],
            "inputs": [project.project_idea or project.description or project.name],
            "outputs": ["Approved project brief", "Prioritized module list", "Initial risk register"],
        },
        {
            "key": "architecture",
            "title": "Architecture & Data Model",
            "phase": 2,
            "status": "READY",
            "owner_role": "Admin",
            "outcome": "Lock the backend apps, frontend routes, API contracts, and deployment topology before build.",
            "activities": [
                "Design Django apps and DRF endpoints",
                "Design React page and component boundaries",
                "Plan database indexes, realtime channels, and background jobs",
            ],
            "inputs": detected_modules,
            "outputs": ["API contract", "Schema checklist", "Frontend route map"],
        },
        {
            "key": "build",
            "title": "Module Build",
            "phase": 3,
            "status": "READY",
            "owner_role": "Developer",
            "outcome": "Implement the selected modules as testable vertical slices.",
            "activities": feature_chunks,
            "inputs": technologies,
            "outputs": ["Working API endpoints", "Usable React screens", "Role-scoped workflows"],
        },
        {
            "key": "validate",
            "title": "Validation & Hardening",
            "phase": 4,
            "status": "READY",
            "owner_role": "Admin",
            "outcome": "Verify security, performance, edge cases, and approval flow before release.",
            "activities": [
                "Run backend migrations and API smoke tests",
                "Run frontend build and route checks",
                "Review RBAC, audit events, and error handling",
            ],
            "inputs": ["Implemented modules", "Demo users", "Deployment controls"],
            "outputs": ["QA signoff", "Known issue list", "Release decision"],
        },
        {
            "key": "release",
            "title": "Release & Operate",
            "phase": 5,
            "status": "READY",
            "owner_role": "Super Admin",
            "outcome": "Ship the project, monitor health, and keep improvements flowing back into the backlog.",
            "activities": [
                "Approve documents and enable deployment",
                "Monitor tickets, logs, notifications, and health score",
                "Generate follow-up tasks from production feedback",
            ],
            "inputs": ["Approved release", "Deployment branch", "Operational metrics"],
            "outputs": ["Production release", "Operational dashboard", "Next iteration backlog"],
        },
    ]
    return flow


def broadcast_project_update(project, event_type):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    recipients = {project.owner_id, project.created_by_id, project.client_id}
    recipients.update(project.admins.values_list("id", flat=True))
    recipients.update(project.developers.values_list("id", flat=True))
    payload = {
        "id": project.id,
        "name": project.name,
        "connection_status": project.connection_status,
        "progress": project.progress,
        "selected_branch": project.selected_branch,
        "last_commit_sha": project.last_commit_sha,
    }
    for user_id in {item for item in recipients if item}:
        try:
            async_to_sync(channel_layer.group_send)(
                f"user_{user_id}",
                {
                    "type": "project.updated",
                    "project": payload,
                    "event": event_type,
                },
            )
        except Exception:
            pass
