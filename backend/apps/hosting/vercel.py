from datetime import datetime, timedelta, timezone as dt_timezone
import hashlib
import logging
import re
import time
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.core.cache import cache
from django.db import OperationalError, close_old_connections
from django.utils import timezone

from apps.api_keys.utils import _fernet

from .models import HostedProject, HostingStatus, VercelDeployment, VercelProject, VercelProjectLink


logger = logging.getLogger(__name__)
VERCEL_DOMAIN_SUFFIX = "vercel.app"
MAX_HOSTED_PROJECT_NAME_LENGTH = 180
MAX_DOMAIN_LENGTH = 255
DB_LOCK_RETRY_ATTEMPTS = 5
DB_LOCK_RETRY_BASE_DELAY_SECONDS = 0.12


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
                try:
                    return response.json()
                except ValueError as exc:
                    logger.exception(
                        "Vercel API returned invalid JSON.",
                        extra={
                            "vercel_path": path,
                            "vercel_status_code": response.status_code,
                        },
                    )
                    raise VercelApiError(
                        "Vercel API returned invalid JSON.",
                        response.status_code,
                        {"detail": response.text[:500]},
                    ) from exc
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
            if not isinstance(payload, dict):
                logger.warning(
                    "Vercel projects response was not an object.",
                    extra={"vercel_payload_type": type(payload).__name__},
                )
                break
            page_projects = payload.get("projects") or []
            if not isinstance(page_projects, list):
                logger.warning(
                    "Vercel projects page had invalid projects field.",
                    extra={"vercel_payload_type": type(page_projects).__name__},
                )
                page_projects = []
            projects.extend(page_projects)
            pagination = _safe_mapping(payload.get("pagination"))
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
        payload = self.request("GET", "/v6/deployments", params=params)
        if not isinstance(payload, dict):
            logger.warning(
                "Vercel deployments response was not an object.",
                extra={
                    "vercel_project_id": project_id,
                    "vercel_project_name": project_name,
                    "vercel_payload_type": type(payload).__name__,
                },
            )
            return []
        deployments = payload.get("deployments") or []
        if not isinstance(deployments, list):
            logger.warning(
                "Vercel deployments field was not a list.",
                extra={
                    "vercel_project_id": project_id,
                    "vercel_project_name": project_name,
                    "vercel_payload_type": type(deployments).__name__,
                },
            )
            return []
        return deployments

    def list_project_domains(self, project_id_or_name):
        payload = self.request("GET", f"/v9/projects/{project_id_or_name}/domains")
        if not isinstance(payload, dict):
            logger.warning(
                "Vercel domains response was not an object.",
                extra={
                    "vercel_project_id": project_id_or_name,
                    "vercel_payload_type": type(payload).__name__,
                },
            )
            return []
        domains = payload.get("domains") or []
        if not isinstance(domains, list):
            logger.warning(
                "Vercel domains field was not a list.",
                extra={
                    "vercel_project_id": project_id_or_name,
                    "vercel_payload_type": type(domains).__name__,
                },
            )
            return []
        return domains

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
    project_items = client.list_projects() or []
    if not isinstance(project_items, list):
        logger.warning(
            "Vercel project list was not a list.",
            extra={"vercel_payload_type": type(project_items).__name__},
        )
        return synced

    for item in project_items:
        try:
            project = upsert_vercel_project(item)
        except ValueError as exc:
            logger.warning(
                "Skipping invalid Vercel project metadata.",
                extra=_vercel_log_context(item, error_cause=str(exc)),
            )
            continue
        except Exception as exc:
            logger.exception(
                "Skipping Vercel project because project metadata could not be parsed.",
                extra=_vercel_log_context(item, error_cause=str(exc)),
            )
            continue

        synced.append(project.id)

        try:
            sync_project_domains(project, client)
        except VercelApiError as exc:
            logger.warning(
                "Vercel project domain sync failed; continuing with next step.",
                extra=_vercel_log_context(project=project, error_cause=str(exc)),
            )
        except Exception as exc:
            logger.exception(
                "Vercel project domain sync failed; continuing with next step.",
                extra=_vercel_log_context(project=project, error_cause=str(exc)),
            )

        try:
            sync_project_deployments(project, client)
        except VercelApiError as exc:
            logger.warning(
                "Vercel project deployment sync failed; continuing with next project.",
                extra=_vercel_log_context(project=project, error_cause=str(exc)),
            )
        except Exception as exc:
            logger.exception(
                "Vercel project deployment sync failed; continuing with next project.",
                extra=_vercel_log_context(project=project, error_cause=str(exc)),
            )

    try:
        from .providers import ensure_default_providers, sync_vercel_links

        ensure_default_providers()
        sync_vercel_links()
    except Exception as exc:
        logger.exception(
            "Vercel provider link refresh failed after project sync.",
            extra={"error_cause": str(exc)},
        )
    return synced


def upsert_vercel_project(item):
    item = _require_mapping(item, "Vercel project item")
    project_name = _clean_text(item.get("name"))
    vercel_id = _clean_text(item.get("id") or project_name)
    if not vercel_id:
        raise ValueError("Vercel project is missing both id and name.")

    project_name = _truncate(project_name or vercel_id, MAX_HOSTED_PROJECT_NAME_LENGTH)
    latest = _extract_latest_deployment(item)
    deployment_url = _extract_deployment_url(latest)
    production_domain = _extract_production_domain(item, deployment_url, project_name, vercel_id)
    context = _vercel_log_context(
        item,
        deployment_url=deployment_url,
        production_domain=production_domain,
    )
    hosted = _with_db_lock_retry(
        lambda: _ensure_hosted_project(item, production_domain, deployment_url),
        context,
        "ensure hosted project",
    )
    account = _safe_mapping(item.get("account"))
    project, _ = _with_db_lock_retry(
        lambda: VercelProject.objects.update_or_create(
            vercel_id=vercel_id,
            defaults={
                "hosted_project": hosted,
                "name": project_name,
                "account_id": _clean_text(item.get("accountId") or account.get("id")),
                "team_id": _clean_text(item.get("teamId")),
                "framework": _clean_text(item.get("framework")),
                "production_domain": production_domain or "",
                "latest_deployment_id": _clean_text(latest.get("id") or latest.get("uid")),
                "latest_deployment_url": deployment_url,
                "latest_deployment_status": _clean_text(latest.get("readyState") or latest.get("state")),
                "raw": item,
                "last_synced_at": timezone.now(),
            },
        ),
        context,
        "upsert Vercel project",
    )
    _with_db_lock_retry(
        lambda: HostingStatus.objects.get_or_create(project=project),
        _vercel_log_context(
            item,
            project=project,
            deployment_url=deployment_url,
            production_domain=production_domain,
        ),
        "ensure Vercel hosting status",
    )
    logger.info(
        "Vercel project synced.",
        extra=_vercel_log_context(
            item,
            project=project,
            deployment_url=deployment_url,
            production_domain=production_domain,
        ),
    )
    return project


def sync_project_domains(project, client=None):
    client = client or VercelClient(team_id=project.team_id)
    domains = client.list_project_domains(project.vercel_id) or []
    seen = set()
    for item in domains:
        if not isinstance(item, dict):
            logger.warning(
                "Skipping malformed Vercel domain item.",
                extra=_vercel_log_context(
                    project=project,
                    error_cause=f"Expected object, received {type(item).__name__}.",
                ),
            )
            continue
        domain = _normalize_domain(item.get("name") or item.get("domain"))
        if not domain:
            logger.warning(
                "Skipping Vercel domain item without a domain value.",
                extra=_vercel_log_context(project=project, error_cause="Missing domain/name."),
            )
            continue
        seen.add(domain)
        tag = "primary" if domain == project.production_domain else "custom"
        _with_db_lock_retry(
            lambda: VercelProjectLink.objects.update_or_create(
                project=project,
                domain=domain,
                defaults={"url": _absolute_url(domain), "tag": tag, "is_active": True},
            ),
            _vercel_log_context(
                project=project,
                deployment_url=_absolute_url(domain),
                production_domain=domain,
            ),
            "upsert Vercel project domain",
        )
    if project.latest_deployment_url:
        parsed = urlparse(project.latest_deployment_url)
        if parsed.netloc and parsed.netloc not in seen:
            _with_db_lock_retry(
                lambda: VercelProjectLink.objects.update_or_create(
                    project=project,
                    domain=parsed.netloc,
                    defaults={"url": project.latest_deployment_url, "tag": "preview", "is_active": True},
                ),
                _vercel_log_context(
                    project=project,
                    deployment_url=project.latest_deployment_url,
                    production_domain=parsed.netloc,
                ),
                "upsert Vercel preview domain",
            )
    return list(project.links.all())


def sync_project_deployments(project, client=None):
    client = client or VercelClient(team_id=project.team_id)
    deployments = client.list_deployments(project_id=project.vercel_id) or []
    for item in deployments:
        if not isinstance(item, dict):
            logger.warning(
                "Skipping malformed Vercel deployment item.",
                extra=_vercel_log_context(
                    project=project,
                    error_cause=f"Expected object, received {type(item).__name__}.",
                ),
            )
            continue
        deployment_id = _clean_text(item.get("uid") or item.get("id"))
        if not deployment_id:
            logger.warning(
                "Skipping Vercel deployment without an id.",
                extra=_vercel_log_context(project=project, error_cause="Missing deployment id."),
            )
            continue
        deployment_url = _absolute_url(item.get("url"))
        _with_db_lock_retry(
            lambda: VercelDeployment.objects.update_or_create(
                deployment_id=deployment_id,
                defaults={
                    "project": project,
                    "url": deployment_url,
                    "status": _clean_text(item.get("readyState") or item.get("state")) or "UNKNOWN",
                    "target": _clean_text(item.get("target")),
                    "meta": _safe_mapping(item.get("meta")),
                    "inspector_url": _absolute_url(item.get("inspectorUrl")),
                    "error_message": _clean_text(item.get("errorMessage")),
                    "created_at_vercel": _from_epoch_ms(item.get("createdAt")),
                    "ready_at": _from_epoch_ms(item.get("ready")),
                    "last_synced_at": timezone.now(),
                    "raw": item,
                },
            ),
            _vercel_log_context(
                project=project,
                deployment_url=deployment_url,
                production_domain=project.production_domain,
            ),
            "upsert Vercel deployment",
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
        project.hosted_project.status = HostedProject.Status.LIVE if enabled else HostedProject.Status.DISABLED
        project.hosted_project.tag = "active" if enabled else "disabled"
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
    item = _safe_mapping(item)
    name = _truncate(
        _clean_text(item.get("name") or item.get("id")) or "vercel-project",
        MAX_HOSTED_PROJECT_NAME_LENGTH,
    )
    domain = (
        _normalize_domain(domain)
        or _domain_from_url(deploy_url)
        or _fallback_vercel_domain(name, item.get("id"))
    )
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
    if hosted.status != HostedProject.Status.LIVE:
        hosted.status = HostedProject.Status.LIVE
        changed.append("status")
    if hosted.tag != "active":
        hosted.tag = "active"
        changed.append("tag")
    if changed:
        hosted.save(update_fields=changed)
    return hosted


def _absolute_url(value):
    value = _clean_text(value)
    if not value:
        return ""
    if value.startswith(("http://", "https://")):
        return value
    if value.startswith("//"):
        return f"https:{value}"
    return f"https://{value}"


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


def _with_db_lock_retry(operation, context, operation_name):
    attempts = _positive_int_setting("VERCEL_DB_LOCK_RETRY_ATTEMPTS", DB_LOCK_RETRY_ATTEMPTS)
    base_delay = _positive_float_setting(
        "VERCEL_DB_LOCK_RETRY_BASE_DELAY_SECONDS",
        DB_LOCK_RETRY_BASE_DELAY_SECONDS,
    )
    context = dict(context or {})
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except OperationalError as exc:
            if not _is_database_locked(exc) or attempt >= attempts:
                raise
            close_old_connections()
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning(
                "Transient database lock during Vercel sync; retrying.",
                extra={
                    **context,
                    "operation": operation_name,
                    "attempt": attempt,
                    "max_attempts": attempts,
                    "retry_delay_seconds": round(delay, 3),
                    "error_cause": str(exc),
                },
            )
            time.sleep(delay)


def _is_database_locked(exc):
    message = str(exc).lower()
    return "database is locked" in message or "database table is locked" in message


def _positive_int_setting(name, default):
    try:
        value = int(getattr(settings, name, default))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _positive_float_setting(name, default):
    try:
        value = float(getattr(settings, name, default))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _require_mapping(value, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object, received {type(value).__name__}.")
    if not value:
        raise ValueError(f"{label} is empty.")
    return value


def _safe_mapping(value):
    return value if isinstance(value, dict) else {}


def _clean_text(value):
    if value is None:
        return ""
    return str(value).strip()


def _truncate(value, max_length):
    value = _clean_text(value)
    return value[:max_length]


def _first_mapping(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return next((item for item in value if isinstance(item, dict)), {})
    return {}


def _extract_latest_deployment(item):
    latest = _first_mapping(item.get("latestDeployments"))
    if latest:
        return latest

    production = _production_target(item)
    latest = _first_mapping(production.get("deployment"))
    if latest:
        return latest

    return {}


def _extract_deployment_url(latest):
    latest = _safe_mapping(latest)
    url = _clean_text(latest.get("url") or latest.get("deploymentHostname"))
    if not url:
        url = _first_string(latest.get("aliases") or latest.get("alias"))
    return _absolute_url(url)


def _extract_production_domain(item, deployment_url, project_name, vercel_id):
    production = item.get("targets")
    production = production.get("production") if isinstance(production, dict) else None
    if isinstance(production, str):
        production_domain = _normalize_domain(production)
    else:
        production_data = _safe_mapping(production)
        production_domain = _normalize_domain(
            production_data.get("domain")
            or production_data.get("url")
            or production_data.get("deploymentHostname")
        )
    return (
        production_domain
        or _domain_from_url(deployment_url)
        or _fallback_vercel_domain(project_name, vercel_id)
    )


def _production_target(item):
    targets = _safe_mapping(item.get("targets"))
    return _safe_mapping(targets.get("production"))


def _normalize_domain(value):
    value = _clean_text(value).lower()
    if not value:
        return ""
    parsed = urlparse(value if "://" in value else f"https://{value}")
    domain = parsed.netloc or parsed.path.split("/", 1)[0]
    return _truncate(domain.strip("."), MAX_DOMAIN_LENGTH)


def _domain_from_url(value):
    value = _clean_text(value)
    if not value:
        return ""
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return _normalize_domain(parsed.netloc)


def _fallback_vercel_domain(project_name, vercel_id):
    label_source = _clean_text(project_name or vercel_id) or "vercel-project"
    label = re.sub(r"[^a-z0-9-]+", "-", label_source.lower())
    label = re.sub(r"-{2,}", "-", label).strip("-") or "vercel-project"
    vercel_id = _clean_text(vercel_id)
    if vercel_id and vercel_id.lower() not in label:
        id_label = re.sub(r"[^a-z0-9-]+", "-", vercel_id.lower()).strip("-")
        if id_label:
            label = f"{label}-{id_label}"
    domain = f"{label}.{VERCEL_DOMAIN_SUFFIX}"
    return _truncate(domain, MAX_DOMAIN_LENGTH)


def _first_string(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return next((_clean_text(item) for item in value if _clean_text(item)), "")
    return ""


def _vercel_log_context(item=None, project=None, deployment_url="", production_domain="", error_cause=""):
    item_data = _safe_mapping(item)
    return {
        "vercel_project_name": (
            _clean_text(getattr(project, "name", ""))
            or _clean_text(item_data.get("name"))
        ),
        "vercel_project_id": (
            _clean_text(getattr(project, "vercel_id", ""))
            or _clean_text(item_data.get("id"))
        ),
        "deployment_url": (
            _clean_text(deployment_url)
            or _clean_text(getattr(project, "latest_deployment_url", ""))
        ),
        "production_domain": (
            _clean_text(production_domain)
            or _clean_text(getattr(project, "production_domain", ""))
        ),
        "error_cause": _clean_text(error_cause),
    }
