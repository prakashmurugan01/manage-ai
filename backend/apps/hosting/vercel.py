from datetime import datetime, timedelta, timezone as dt_timezone
import hashlib
import time
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.api_keys.utils import _fernet

from .models import HostedProject, HostingStatus, VercelDeployment, VercelProject, VercelProjectLink


class VercelApiError(Exception):
    def __init__(self, message, status_code=None, payload=None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload or {}


class VercelClient:
    base_url = "https://api.vercel.com"

    def __init__(self, token=None, team_id=None):
        self.token = token or getattr(settings, "VERCEL_API_TOKEN", "")
        self.team_id = team_id or getattr(settings, "VERCEL_TEAM_ID", "")
        if not self.token:
            raise VercelApiError("VERCEL_API_TOKEN is not configured.")

    def request(self, method, path, params=None, json=None, data=None, headers=None, retries=3, timeout=20):
        params = dict(params or {})
        if self.team_id and "teamId" not in params:
            params["teamId"] = self.team_id
        request_headers = {"Authorization": f"Bearer {self.token}"}
        if headers:
            request_headers.update(headers)
        elif json is not None:
            request_headers["Content-Type"] = "application/json"
        url = f"{self.base_url}{path}"
        last_error = None
        for attempt in range(retries):
            try:
                response = requests.request(method, url, headers=request_headers, params=params, json=json, data=data, timeout=timeout)
                if response.status_code in {429, 500, 502, 503, 504} and attempt < retries - 1:
                    time.sleep(2**attempt)
                    continue
                if response.status_code >= 400:
                    try:
                        payload = response.json()
                    except ValueError:
                        payload = {"detail": response.text}
                    message = payload.get("error", {}).get("message") or payload.get("message") or payload.get("detail") or "Vercel API request failed."
                    raise VercelApiError(message, response.status_code, payload)
                if response.status_code == 204:
                    return {}
                return response.json()
            except requests.RequestException as exc:
                last_error = exc
                if attempt < retries - 1:
                    time.sleep(2**attempt)
                    continue
        raise VercelApiError(str(last_error or "Vercel API request failed."))

    def list_projects(self, limit=100):
        cache_key = f"vercel:projects:{self.team_id or 'personal'}:{limit}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached
        projects = []
        params = {"limit": limit}
        while True:
            payload = self.request("GET", "/v10/projects", params=params)
            projects.extend(payload.get("projects", []))
            pagination = payload.get("pagination") or {}
            next_until = pagination.get("next")
            if not next_until:
                break
            params["until"] = next_until
        _cache_set(cache_key, projects, getattr(settings, "VERCEL_CACHE_SECONDS", 45))
        return projects

    def list_deployments(self, project_id=None, project_name=None, limit=20):
        params = {"limit": limit}
        if project_id:
            params["projectId"] = project_id
        if project_name:
            params["app"] = project_name
        return self.request("GET", "/v6/deployments", params=params).get("deployments", [])

    def list_project_domains(self, project_id_or_name):
        payload = self.request("GET", f"/v9/projects/{project_id_or_name}/domains")
        return payload.get("domains", [])

    def add_project_domain(self, project_id_or_name, domain):
        return self.request("POST", f"/v10/projects/{project_id_or_name}/domains", json={"name": domain})

    def remove_project_domain(self, project_id_or_name, domain):
        return self.request("DELETE", f"/v9/projects/{project_id_or_name}/domains/{domain}")

    def redeploy(self, deployment_id):
        return self.request("POST", "/v13/deployments", json={"deploymentId": deployment_id})

    def deployment_events(self, deployment_id, limit=100):
        return self.request("GET", f"/v3/deployments/{deployment_id}/events", params={"limit": limit})

    def get_deployment(self, deployment_id_or_url):
        return self.request("GET", f"/v13/deployments/{deployment_id_or_url}")

    def upload_deployment_file(self, relative_path, content):
        digest = hashlib.sha1(content).hexdigest()
        self.request(
            "POST",
            "/v2/files",
            data=content,
            headers={
                "Content-Type": "application/octet-stream",
                "Content-Length": str(len(content)),
                "x-vercel-digest": digest,
            },
            timeout=60,
        )
        return {"file": relative_path.replace("\\", "/"), "sha": digest, "size": len(content)}

    def create_file_deployment(self, name, files, project=None, target="production", build_command="", output_directory="", framework=None, meta=None):
        project_settings = {}
        if build_command and build_command.lower() != "no build required":
            project_settings["buildCommand"] = build_command
        if output_directory and output_directory != ".":
            project_settings["outputDirectory"] = output_directory
        project_settings["framework"] = framework
        body = {
            "name": name,
            "files": files,
            "target": target,
            "meta": meta or {},
        }
        if project:
            body["project"] = project
        body["projectSettings"] = project_settings
        return self.request("POST", "/v13/deployments", params={"skipAutoDetectionConfirmation": "1"}, json=body, timeout=60)


def sync_vercel_projects(client=None):
    client = client or VercelClient()
    synced = []
    for item in client.list_projects():
        project = upsert_vercel_project(item)
        sync_project_domains(project, client)
        sync_project_deployments(project, client)
        synced.append(project.id)
    try:
        from .providers import ensure_default_providers, sync_vercel_links

        ensure_default_providers()
        sync_vercel_links()
    except Exception:
        pass
    return synced


def upsert_vercel_project(item):
    vercel_id = item.get("id") or item.get("name")
    latest = item.get("latestDeployments") or item.get("targets", {}).get("production", {}).get("deployment") or {}
    if isinstance(latest, list):
        latest = latest[0] if latest else {}
    production_domain = item.get("targets", {}).get("production", {}).get("domain") or item.get("name", "")
    deployment_url = _absolute_url(latest.get("url") or latest.get("deploymentHostname") or "")
    hosted = _ensure_hosted_project(item, production_domain, deployment_url)
    project, _ = VercelProject.objects.update_or_create(
        vercel_id=vercel_id,
        defaults={
            "hosted_project": hosted,
            "name": item.get("name", vercel_id),
            "account_id": str(item.get("accountId") or item.get("account", {}).get("id") or ""),
            "team_id": str(item.get("teamId") or ""),
            "framework": item.get("framework") or "",
            "production_domain": production_domain or "",
            "latest_deployment_id": latest.get("id") or latest.get("uid") or "",
            "latest_deployment_url": deployment_url,
            "latest_deployment_status": latest.get("readyState") or latest.get("state") or "",
            "raw": item,
            "last_synced_at": timezone.now(),
        },
    )
    HostingStatus.objects.get_or_create(project=project)
    return project


def sync_project_domains(project, client=None):
    client = client or VercelClient(team_id=project.team_id)
    domains = client.list_project_domains(project.vercel_id)
    seen = set()
    for item in domains:
        domain = item.get("name") or item.get("domain")
        if not domain:
            continue
        seen.add(domain)
        tag = "primary" if domain == project.production_domain else "custom"
        VercelProjectLink.objects.update_or_create(
            project=project,
            domain=domain,
            defaults={"url": _absolute_url(domain), "tag": tag, "is_active": True},
        )
    if project.latest_deployment_url:
        parsed = urlparse(project.latest_deployment_url)
        if parsed.netloc and parsed.netloc not in seen:
            VercelProjectLink.objects.update_or_create(
                project=project,
                domain=parsed.netloc,
                defaults={"url": project.latest_deployment_url, "tag": "preview", "is_active": True},
            )
    return list(project.links.all())


def sync_project_deployments(project, client=None):
    client = client or VercelClient(team_id=project.team_id)
    deployments = client.list_deployments(project_id=project.vercel_id)
    for item in deployments:
        deployment_id = item.get("uid") or item.get("id")
        if not deployment_id:
            continue
        VercelDeployment.objects.update_or_create(
            deployment_id=deployment_id,
            defaults={
                "project": project,
                "url": _absolute_url(item.get("url") or ""),
                "status": item.get("readyState") or item.get("state") or "UNKNOWN",
                "target": item.get("target") or "",
                "meta": item.get("meta") or {},
                "inspector_url": item.get("inspectorUrl") or "",
                "error_message": item.get("errorMessage") or "",
                "created_at_vercel": _from_epoch_ms(item.get("createdAt")),
                "ready_at": _from_epoch_ms(item.get("ready")),
                "last_synced_at": timezone.now(),
                "raw": item,
            },
        )
    return list(project.deployments.all()[:20])


def set_vercel_access(project, enabled, user=None, redirect_url="", reason=""):
    status_obj, _ = HostingStatus.objects.get_or_create(project=project)
    client = VercelClient(team_id=project.team_id)
    errors = []
    for link in project.links.filter(tag__in=["primary", "custom"]):
        try:
            if enabled:
                client.add_project_domain(project.vercel_id, link.domain)
                link.is_active = True
                link.disabled_at = None
            else:
                client.remove_project_domain(project.vercel_id, link.domain)
                link.is_active = False
                link.disabled_at = timezone.now()
            link.save(update_fields=["is_active", "disabled_at"])
        except VercelApiError as exc:
            errors.append({"domain": link.domain, "detail": str(exc), "status_code": exc.status_code})
    status_obj.is_enabled = enabled
    status_obj.mode = HostingStatus.Mode.ACTIVE if enabled else HostingStatus.Mode.DISABLED
    status_obj.disabled_redirect_url = "" if enabled else redirect_url
    status_obj.disabled_reason = "" if enabled else reason
    status_obj.last_action_at = timezone.now()
    status_obj.last_action_by = user if getattr(user, "is_authenticated", False) else None
    status_obj.save()
    if project.hosted_project:
        project.hosted_project.link_is_active = enabled
        project.hosted_project.status = HostedProject.Status.LIVE if enabled else HostedProject.Status.SUSPENDED
        project.hosted_project.tag = "active" if enabled else "maintenance"
        project.hosted_project.save(update_fields=["link_is_active", "status", "tag"])
    return status_obj, errors


def token_from_hosted_project(hosted_project):
    if not hosted_project or not hosted_project.access_key_encrypted:
        return ""
    try:
        return _fernet().decrypt(hosted_project.access_key_encrypted.encode()).decode()
    except Exception:
        return ""


def _ensure_hosted_project(item, domain, deploy_url):
    name = item.get("name") or item.get("id")
    domain = domain or f"{name}.vercel.app"
    hosted, _ = HostedProject.objects.get_or_create(
        domain=domain,
        defaults={
            "name": name,
            "client_name": "Vercel",
            "hosting_platform": HostedProject.Platform.VERCEL,
            "deploy_url": deploy_url,
            "status": HostedProject.Status.LIVE,
            "tag": "active",
            "expiry_date": timezone.localdate() + timedelta(days=365),
        },
    )
    changed = []
    if hosted.hosting_platform != HostedProject.Platform.VERCEL:
        hosted.hosting_platform = HostedProject.Platform.VERCEL
        changed.append("hosting_platform")
    if deploy_url and hosted.deploy_url != deploy_url:
        hosted.deploy_url = deploy_url
        changed.append("deploy_url")
    if changed:
        hosted.save(update_fields=changed)
    return hosted


def _absolute_url(value):
    if not value:
        return ""
    return value if value.startswith(("http://", "https://")) else f"https://{value}"


def _from_epoch_ms(value):
    if not value:
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=dt_timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _cache_get(key):
    try:
        return cache.get(key)
    except Exception:
        return None


def _cache_set(key, value, timeout):
    try:
        cache.set(key, value, timeout)
    except Exception:
        pass
