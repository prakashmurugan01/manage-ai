import time
import socket
import ssl
import tempfile
import zipfile
from datetime import datetime, timedelta, timezone as dt_timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from celery import shared_task
from django.utils import timezone

from apps.notifications.tasks import check_hosting_expiry

from .models import DeploymentRun, DomainStatus, EmailAccount, HostedProject, HostingLifecycle, HostingLink, ProjectUpload, VercelDeployment, VercelProjectLink
from .providers import failover_all_projects, sync_all_providers
from .vercel import VercelApiError, VercelClient, sync_vercel_projects


@shared_task(name="hosting.tasks.check_hosting_expiry")
def check_hosting_expiry_alias():
    return check_hosting_expiry.delay().id


@shared_task(name="hosting.tasks.check_hosted_project_health")
def check_hosted_project_health(project_id):
    project = HostedProject.objects.get(id=project_id)
    started = time.monotonic()
    status_value = HostedProject.ServerStatus.UNKNOWN
    status_code = None

    try:
        target = project.deploy_url or f"https://{project.domain}"
        parsed = urlparse(target)
        if not parsed.scheme:
            target = f"https://{target}"
        response = requests.get(target, timeout=8, allow_redirects=True)
        status_code = response.status_code
        elapsed_ms = int((time.monotonic() - started) * 1000)
        if response.status_code >= 500:
            status_value = HostedProject.ServerStatus.OFFLINE
        elif elapsed_ms > 2500:
            status_value = HostedProject.ServerStatus.SLOW
        else:
            status_value = HostedProject.ServerStatus.ONLINE
    except requests.RequestException:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        status_value = HostedProject.ServerStatus.OFFLINE

    previous_status = project.server_status
    previous_checks = max(project.downtime_count, 0)
    project.server_status = status_value
    project.response_time_ms = elapsed_ms
    project.last_checked_at = timezone.now()

    if status_value == HostedProject.ServerStatus.OFFLINE:
        project.downtime_count = previous_checks + 1
        project.link_is_active = False
        project.tag = "maintenance"
    elif project.status == HostedProject.Status.LIVE:
        project.tag = "active"

    project.uptime_percentage = _next_uptime(project.uptime_percentage, status_value)
    project.save(
        update_fields=[
            "server_status",
            "response_time_ms",
            "last_checked_at",
            "downtime_count",
            "link_is_active",
            "tag",
            "uptime_percentage",
        ]
    )

    if status_value != previous_status:
        event_type = HostingLifecycle.Event.LINK_DISABLED if status_value == HostedProject.ServerStatus.OFFLINE else HostingLifecycle.Event.HEALTH_CHECK
        HostingLifecycle.objects.create(
            project=project,
            event_type=event_type,
            notes=f"Health changed from {previous_status} to {status_value}. HTTP {status_code or 'n/a'}, {elapsed_ms}ms.",
        )
        if status_value == HostedProject.ServerStatus.OFFLINE:
            _create_outage_notification(project, elapsed_ms)
    return {"project_id": project.id, "server_status": status_value, "response_time_ms": elapsed_ms}


@shared_task(name="hosting.tasks.check_all_hosted_project_health")
def check_all_hosted_project_health():
    queued = 0
    for project_id in HostedProject.objects.filter(archived_at__isnull=True, link_is_active=True).values_list("id", flat=True):
        check_hosted_project_health.delay(project_id)
        queued += 1
    return queued


@shared_task(name="hosting.tasks.sync_vercel_projects")
def sync_vercel_projects_task():
    try:
        synced = sync_vercel_projects()
    except VercelApiError as exc:
        return {"synced": 0, "error": str(exc), "status_code": exc.status_code}
    return {"synced": len(synced)}


@shared_task(name="hosting.tasks.sync_all_hosting_providers")
def sync_all_hosting_providers_task():
    return sync_all_providers()


@shared_task(name="hosting.tasks.evaluate_hosting_failover")
def evaluate_hosting_failover_task():
    states = failover_all_projects()
    return {"evaluated": len(states)}


@shared_task(name="hosting.tasks.analyze_project_upload")
def analyze_project_upload(upload_id):
    upload = ProjectUpload.objects.get(id=upload_id)
    upload.status = ProjectUpload.Status.PROCESSING
    upload.save(update_fields=["status"])
    try:
        names = _uploaded_file_names(upload)
        stack, project_type = _detect_stack(names)
        suggestions = _provider_suggestions(project_type)
        upload.detected_stack = stack
        upload.project_type = project_type
        upload.suggested_providers = suggestions
        upload.analysis = {
            "file_count": len(names),
            "entry_preview": names[:40],
            "build_command": _suggest_build_command(project_type),
            "output_directory": _suggest_output_dir(project_type),
        }
        upload.status = ProjectUpload.Status.ANALYZED
        upload.analyzed_at = timezone.now()
        upload.error_message = ""
        upload.save(update_fields=["detected_stack", "project_type", "suggested_providers", "analysis", "status", "analyzed_at", "error_message"])
        return {"upload_id": str(upload.id), "project_type": project_type, "detected_stack": stack}
    except Exception as exc:
        upload.status = ProjectUpload.Status.FAILED
        upload.error_message = str(exc)
        upload.save(update_fields=["status", "error_message"])
        return {"upload_id": str(upload.id), "error": str(exc)}


@shared_task(name="hosting.tasks.run_project_deployment")
def run_project_deployment(deployment_id):
    deployment = DeploymentRun.objects.select_related("upload").get(id=deployment_id)
    try:
        if deployment.primary_provider == HostingLink.Provider.VERCEL:
            return _run_vercel_deployment(deployment)
        return _run_simulated_deployment(deployment)
    except Exception as exc:
        _append_deployment_log(deployment, f"Deployment failed: {exc}", level="error")
        deployment.status = DeploymentRun.Status.ERROR
        deployment.error_message = str(exc)
        deployment.completed_at = timezone.now()
        deployment.save(update_fields=["status", "error_message", "completed_at", "logs"])
        return {"deployment_id": str(deployment.id), "status": deployment.status, "error": str(exc)}


@shared_task(name="hosting.tasks.check_email_account")
def check_email_account(account_id):
    account = EmailAccount.objects.select_related("project").get(id=account_id)
    domain = account.email.split("@")[-1].lower()
    mx_records = _mx_records(domain)
    account.mx_status = "healthy" if mx_records else "misconfigured"
    account.status = EmailAccount.Status.MISCONFIGURED if not mx_records else account.status
    account.last_checked_at = timezone.now()
    account.metadata = {**account.metadata, "mx_records": mx_records}
    account.save(update_fields=["mx_status", "status", "last_checked_at", "metadata", "updated_at"])
    HostingLifecycle.objects.create(project=account.project, event_type=HostingLifecycle.Event.EMAIL_CHECK, notes=f"{account.email} MX status: {account.mx_status}.")
    return {"email": account.email, "mx_status": account.mx_status, "mx_records": mx_records}


@shared_task(name="hosting.tasks.check_all_email_accounts")
def check_all_email_accounts():
    queued = 0
    for account_id in EmailAccount.objects.values_list("id", flat=True):
        check_email_account.delay(account_id)
        queued += 1
    return {"queued": queued}


@shared_task(name="hosting.tasks.check_domain_status")
def check_domain_status(project_id):
    project = HostedProject.objects.get(id=project_id)
    domain = project.domain.lower()
    domain_status, _ = DomainStatus.objects.get_or_create(project=project, defaults={"domain": domain})
    mx_records = _mx_records(domain)
    ssl_info = _ssl_status(domain)
    domain_status.domain = domain
    domain_status.mx_records = mx_records
    domain_status.mx_status = DomainStatus.Health.HEALTHY if mx_records else DomainStatus.Health.CRITICAL
    domain_status.ssl_status = ssl_info["status"]
    domain_status.ssl_expires_at = ssl_info["expires_at"]
    domain_status.email_health_score = _email_score(mx_records, domain_status.ssl_status)
    domain_status.last_checked_at = timezone.now()
    domain_status.last_error = ssl_info.get("error", "")
    domain_status.metadata = {**domain_status.metadata, "ssl_issuer": ssl_info.get("issuer", "")}
    domain_status.save(
        update_fields=[
            "domain",
            "mx_records",
            "mx_status",
            "ssl_status",
            "ssl_expires_at",
            "email_health_score",
            "last_checked_at",
            "last_error",
            "metadata",
        ]
    )
    HostingLifecycle.objects.create(project=project, event_type=HostingLifecycle.Event.DOMAIN_CHECK, notes=f"MX {domain_status.mx_status}, SSL {domain_status.ssl_status}.")
    return {"project_id": project.id, "domain": domain, "mx_status": domain_status.mx_status, "ssl_status": domain_status.ssl_status}


@shared_task(name="hosting.tasks.check_all_domain_statuses")
def check_all_domain_statuses():
    queued = 0
    for project_id in HostedProject.objects.filter(archived_at__isnull=True).values_list("id", flat=True):
        check_domain_status.delay(project_id)
        queued += 1
    return {"queued": queued}


@shared_task(name="hosting.tasks.check_vercel_links")
def check_vercel_links():
    checked = 0
    for link in VercelProjectLink.objects.select_related("project", "project__hosted_project").filter(is_active=True):
        _check_vercel_link(link)
        checked += 1
    return {"checked": checked}


@shared_task(name="hosting.tasks.notify_failed_vercel_deployments")
def notify_failed_vercel_deployments():
    failures = VercelDeployment.objects.select_related("project", "project__hosted_project").filter(status__in=["ERROR", "CANCELED"]).order_by("-last_synced_at")[:50]
    count = 0
    for deployment in failures:
        hosted_project = deployment.project.hosted_project
        if hosted_project:
            _create_deployment_failure_notification(hosted_project, deployment)
            count += 1
    return {"notifications": count}


@shared_task(name="hosting.tasks.update_hosting_lifecycle_statuses")
def update_hosting_lifecycle_statuses():
    today = timezone.localdate()
    expired_count = 0
    archived_count = 0
    unstable_count = 0
    for project in HostedProject.objects.filter(expiry_date__lt=today, archived_at__isnull=True).exclude(status=HostedProject.Status.EXPIRED):
        project.status = HostedProject.Status.EXPIRED
        project.tag = "expired"
        project.link_is_active = False
        project.archived_at = timezone.now()
        project.save(update_fields=["status", "tag", "link_is_active", "archived_at"])
        HostingLifecycle.objects.create(project=project, event_type=HostingLifecycle.Event.EXPIRED, notes="Automatically expired and archived.")
        expired_count += 1
        archived_count += 1

    for project in HostedProject.objects.filter(archived_at__isnull=True, downtime_count__gte=3):
        if project.tag != "maintenance":
            project.tag = "maintenance"
            project.status = HostedProject.Status.MAINTENANCE
            project.save(update_fields=["tag", "status"])
            HostingLifecycle.objects.create(project=project, event_type=HostingLifecycle.Event.HEALTH_CHECK, notes="Flagged unstable after repeated downtime.")
            unstable_count += 1
    return {"expired": expired_count, "archived": archived_count, "unstable": unstable_count}


def _next_uptime(current, status_value):
    current = float(current or 100)
    sample = 0 if status_value == HostedProject.ServerStatus.OFFLINE else 100
    return round((current * 19 + sample) / 20, 2)


def _create_outage_notification(project, elapsed_ms):
    from apps.notifications.models import Notification
    from apps.notifications.tasks import _broadcast, _notification_user

    user = _notification_user(project)
    if not user:
        return
    notification = Notification.objects.create(
        recipient=user,
        hosted_project=project,
        type=Notification.Type.ALERT,
        urgency="critical",
        title=f"{project.name} is offline",
        message=f"{project.domain} failed the automated health check after {elapsed_ms}ms. The hosting link was switched off.",
    )
    _broadcast(notification)


def _check_vercel_link(link):
    started = time.monotonic()
    try:
        response = requests.get(link.url, timeout=8, allow_redirects=True)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        is_down = response.status_code >= 500
        link.last_http_status = response.status_code
    except requests.RequestException:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        is_down = True
        link.last_http_status = None
    link.response_time_ms = elapsed_ms
    link.last_checked_at = timezone.now()
    link.uptime_percentage = _next_uptime(link.uptime_percentage, HostedProject.ServerStatus.OFFLINE if is_down else HostedProject.ServerStatus.ONLINE)
    link.save(update_fields=["last_http_status", "response_time_ms", "last_checked_at", "uptime_percentage"])
    hosted_project = link.project.hosted_project
    if hosted_project and is_down:
        hosted_project.server_status = HostedProject.ServerStatus.OFFLINE
        hosted_project.downtime_count += 1
        hosted_project.last_checked_at = timezone.now()
        hosted_project.response_time_ms = elapsed_ms
        hosted_project.uptime_percentage = _next_uptime(hosted_project.uptime_percentage, HostedProject.ServerStatus.OFFLINE)
        hosted_project.save(update_fields=["server_status", "downtime_count", "last_checked_at", "response_time_ms", "uptime_percentage"])
        _create_outage_notification(hosted_project, elapsed_ms)


def _create_deployment_failure_notification(project, deployment):
    from apps.notifications.models import Notification
    from apps.notifications.tasks import _broadcast, _notification_user

    user = _notification_user(project)
    if not user:
        return
    notification = Notification.objects.create(
        recipient=user,
        hosted_project=project,
        type=Notification.Type.ALERT,
        urgency="critical",
        title=f"{project.name} deployment failed",
        message=f"Vercel deployment {deployment.deployment_id} is {deployment.status}. {deployment.error_message or deployment.url}",
    )
    _broadcast(notification)


def _mx_records(domain):
    try:
        import dns.resolver

        answers = dns.resolver.resolve(domain, "MX")
        return sorted([str(answer.exchange).rstrip(".") for answer in answers])
    except Exception:
        return []


def _ssl_status(domain):
    try:
        context = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=6) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as wrapped:
                cert = wrapped.getpeercert()
        expires_at = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=dt_timezone.utc)
        days_left = (expires_at - datetime.now(dt_timezone.utc)).days
        issuer = " / ".join("=".join(part) for item in cert.get("issuer", []) for part in item)
        if days_left <= 7:
            status = DomainStatus.Health.CRITICAL
        elif days_left <= 30:
            status = DomainStatus.Health.WARNING
        else:
            status = DomainStatus.Health.HEALTHY
        return {"status": status, "expires_at": expires_at, "issuer": issuer}
    except Exception as exc:
        return {"status": DomainStatus.Health.CRITICAL, "expires_at": None, "error": str(exc)}


def _email_score(mx_records, ssl_status):
    score = 0
    if mx_records:
        score += 65
    if ssl_status == DomainStatus.Health.HEALTHY:
        score += 35
    elif ssl_status == DomainStatus.Health.WARNING:
        score += 15
    return min(score, 100)


def _run_vercel_deployment(deployment):
    project = deployment.project or _project_from_deployment(deployment)
    deployment.project = project
    deployment.save(update_fields=["project"])
    client = VercelClient()
    _set_deployment_step(deployment, DeploymentRun.Status.UPLOADING, 12, "Extracting project package for Vercel upload.")
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        files_on_disk = _extract_upload_to_directory(deployment.upload, root)
        if not files_on_disk:
            raise ValueError("No deployable files found in the uploaded package.")
        _set_deployment_step(deployment, DeploymentRun.Status.UPLOADING, 28, f"Uploading {len(files_on_disk)} file(s) to Vercel.")
        vercel_files = []
        for index, file_path in enumerate(files_on_disk, start=1):
            relative = file_path.relative_to(root).as_posix()
            vercel_files.append(client.upload_deployment_file(relative, file_path.read_bytes()))
            if index == 1 or index % 20 == 0 or index == len(files_on_disk):
                progress = 28 + int((index / len(files_on_disk)) * 34)
                _set_deployment_step(deployment, DeploymentRun.Status.UPLOADING, progress, f"Uploaded {index}/{len(files_on_disk)} file(s) to Vercel.")

    _set_deployment_step(deployment, DeploymentRun.Status.DEPLOYING, 68, "Creating Vercel deployment from uploaded file hashes.")
    response = client.create_file_deployment(
        name=_vercel_project_name(project.name or deployment.upload.original_name),
        files=vercel_files,
        target="production",
        build_command=deployment.build_command or _suggest_build_command(deployment.upload.project_type),
        output_directory=deployment.output_directory or _suggest_output_dir(deployment.upload.project_type),
        framework=_vercel_framework(deployment.upload.project_type),
        meta={"source": "manageai-upload", "deployment_run": str(deployment.id)},
    )
    vercel_id = response.get("id") or response.get("uid")
    response_project = response.get("project") if isinstance(response.get("project"), dict) else {}
    project_ref = response_project.get("id") or response_project.get("name") or _vercel_project_name(project.name or deployment.upload.original_name)
    deployment_url = _absolute_url(response.get("url") or response.get("alias") or "")
    _set_deployment_step(deployment, DeploymentRun.Status.BUILDING, 82, f"Vercel deployment created: {vercel_id or deployment_url}. Waiting for readiness.")

    latest = response
    for _ in range(18):
        ready_state = (latest.get("readyState") or latest.get("state") or "").upper()
        if ready_state == "READY":
            break
        if ready_state in {"ERROR", "CANCELED"}:
            raise VercelApiError(latest.get("errorMessage") or f"Vercel deployment ended with {ready_state}", payload=latest)
        time.sleep(3)
        if vercel_id:
            latest = client.get_deployment(vercel_id)

    live_url = _absolute_url(latest.get("url") or deployment_url or f"{_vercel_project_name(project.name)}.vercel.app")
    custom_domain_url = ""
    if deployment.domain:
        _set_deployment_step(deployment, DeploymentRun.Status.DEPLOYING, 94, f"Adding custom domain {deployment.domain} to Vercel project.")
        try:
            client.add_project_domain(project_ref, deployment.domain)
            custom_domain_url = _absolute_url(deployment.domain)
            _append_deployment_log(deployment, f"Custom domain attached: {deployment.domain}")
        except VercelApiError as exc:
            _append_deployment_log(deployment, f"Custom domain pending/manual action: {exc}", level="warning")
    final_url = custom_domain_url or live_url
    final_domain = urlparse(final_url).netloc or project.domain
    if project.domain != final_domain and not HostedProject.objects.filter(domain=final_domain).exclude(id=project.id).exists():
        project.domain = final_domain
    project.deploy_url = live_url
    if final_url:
        project.deploy_url = final_url
    project.hosting_platform = HostedProject.Platform.VERCEL
    project.status = HostedProject.Status.LIVE
    project.tag = "active"
    project.link_is_active = True
    project.save(update_fields=["domain", "deploy_url", "hosting_platform", "status", "tag", "link_is_active"])
    deployment.live_url = final_url
    deployment.status = DeploymentRun.Status.LIVE
    deployment.progress = 100
    deployment.completed_at = timezone.now()
    deployment.save(update_fields=["live_url", "status", "progress", "completed_at", "logs"])
    _append_deployment_log(deployment, f"Vercel deployment is live: {final_url}")
    _upsert_deployment_link(project, deployment, final_url, HostingLink.Provider.VERCEL, latest)
    return {"deployment_id": str(deployment.id), "status": deployment.status, "live_url": final_url, "vercel_id": vercel_id}


def _run_simulated_deployment(deployment):
    steps = [
        (DeploymentRun.Status.UPLOADING, 20, "Upload package accepted and staged securely."),
        (DeploymentRun.Status.BUILDING, 48, f"Running build command: {deployment.build_command or _suggest_build_command(deployment.upload.project_type)}"),
        (DeploymentRun.Status.DEPLOYING, 78, f"Deploying to {deployment.primary_provider}."),
        (DeploymentRun.Status.LIVE, 100, "Deployment is live and monitoring has started."),
    ]
    for status_value, progress, message in steps:
        _set_deployment_step(deployment, status_value, progress, message)
    project = deployment.project or _project_from_deployment(deployment)
    live_url = deployment.domain or f"https://{project.domain}"
    deployment.project = project
    deployment.live_url = live_url
    deployment.completed_at = timezone.now()
    deployment.save(update_fields=["project", "live_url", "completed_at"])
    _upsert_deployment_link(project, deployment, live_url, deployment.primary_provider, {"mode": "simulated"})
    if deployment.backup_provider:
        HostingLink.objects.get_or_create(
            project=project,
            provider=deployment.backup_provider,
            domain=f"backup-{project.domain}",
            defaults={
                "priority": 4,
                "label": "Backup deployment",
                "url": live_url,
                "server_type": HostingLink.ServerType.CLOUD,
                "tag": HostingLink.LinkTag.BACKUP,
                "status": HostingLink.Status.ON,
                "health_status": HostingLink.Health.UNKNOWN,
                "metadata": {"deployment_id": str(deployment.id), "source_upload": str(deployment.upload_id)},
            },
        )
    return {"deployment_id": str(deployment.id), "status": deployment.status, "live_url": live_url}


def _extract_upload_to_directory(upload, root):
    source = upload.upload.path
    if zipfile.is_zipfile(source):
        with zipfile.ZipFile(source) as archive:
            _safe_extract_zip(archive, root)
    else:
        target = root / upload.original_name
        target.write_bytes(Path(source).read_bytes())
    files = [path for path in root.rglob("*") if path.is_file() and _is_deployable_file(path)]
    common_root = _common_project_root(root, files)
    if common_root and common_root != root:
        normalized = []
        for file_path in files:
            target = root / file_path.relative_to(common_root)
            target.parent.mkdir(parents=True, exist_ok=True)
            if file_path != target:
                target.write_bytes(file_path.read_bytes())
            normalized.append(target)
        files = normalized
    return sorted(files, key=lambda item: item.as_posix())


def _safe_extract_zip(archive, root):
    root = root.resolve()
    for member in archive.infolist():
        if member.is_dir():
            continue
        target = (root / member.filename).resolve()
        if root not in target.parents and target != root:
            raise ValueError(f"Unsafe path in ZIP: {member.filename}")
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(member) as source_file:
            target.write_bytes(source_file.read())


def _is_deployable_file(path):
    parts = set(path.parts)
    if parts.intersection({"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build"}):
        return False
    return path.stat().st_size <= 25 * 1024 * 1024


def _common_project_root(root, files):
    relatives = [file_path.relative_to(root) for file_path in files]
    roots = {relative.parts[0] for relative in relatives if len(relative.parts) > 1}
    if len(roots) == 1 and len(roots) == len({relative.parts[0] for relative in relatives if relative.parts}):
        return root / next(iter(roots))
    return None


def _upsert_deployment_link(project, deployment, live_url, provider, raw):
    domain = urlparse(live_url).netloc or project.domain
    link, _ = HostingLink.objects.update_or_create(
        project=project,
        provider=provider,
        domain=domain,
        defaults={
            "priority": 1,
            "label": "Primary deployment",
            "url": live_url,
            "server_type": HostingLink.ServerType.CLOUD,
            "tag": HostingLink.LinkTag.PRODUCTION,
            "status": HostingLink.Status.ON,
            "health_status": HostingLink.Health.HEALTHY,
            "is_active": True,
            "metadata": {"deployment_id": str(deployment.id), "source_upload": str(deployment.upload_id), "provider_payload": raw},
        },
    )
    return link


def _absolute_url(value):
    if not value:
        return ""
    value = str(value)
    return value if value.startswith(("http://", "https://")) else f"https://{value}"


def _set_deployment_step(deployment, status_value, progress, message):
    deployment.status = status_value
    deployment.progress = progress
    _append_deployment_log(deployment, message, save=False)
    deployment.save(update_fields=["status", "progress", "logs"])


def _append_deployment_log(deployment, message, level="info", save=True):
    logs = list(deployment.logs or [])
    logs.append({"time": timezone.now().isoformat(), "level": level, "message": message})
    deployment.logs = logs
    if save:
        deployment.save(update_fields=["logs"])


def _vercel_project_name(value):
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in str(value or "manageai-upload"))
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return (cleaned or "manageai-upload")[:80]


def _vercel_framework(project_type):
    return {"react": "vite", "node": None, "static": None, "django": None}.get(project_type)


def _uploaded_file_names(upload):
    path = upload.upload.path
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            return [item.filename for item in archive.infolist() if not item.is_dir()]
    return [upload.original_name]


def _detect_stack(names):
    lowered = [name.lower() for name in names]
    stack = []
    if any(name.endswith("package.json") for name in lowered):
        stack.append("Node.js")
    if any("vite.config" in name or "src/app.jsx" in name or "src/main.jsx" in name for name in lowered):
        stack.append("React")
    if any(name.endswith("manage.py") for name in lowered) or any("requirements.txt" in name for name in lowered):
        stack.append("Django")
    if any(name.endswith("next.config.js") for name in lowered):
        stack.append("Next.js")
    if any(name.endswith("index.html") for name in lowered) and not stack:
        stack.append("Static")
    if "Django" in stack:
        return stack, "django"
    if "Next.js" in stack:
        return stack, "node"
    if "React" in stack:
        return stack, "react"
    if "Node.js" in stack:
        return stack, "node"
    if "Static" in stack:
        return stack, "static"
    return stack or ["Unknown"], "static"


def _provider_suggestions(project_type):
    return {
        "react": ["vercel", "netlify", "cloudflare_pages"],
        "node": ["aws", "digitalocean", "cloudways"],
        "django": ["aws", "digitalocean", "cloudways"],
        "static": ["netlify", "vercel", "aws_s3"],
    }.get(project_type, ["aws", "digitalocean"])


def _suggest_build_command(project_type):
    return {
        "react": "npm install && npm run build",
        "node": "npm install && npm run build",
        "django": "pip install -r requirements.txt && python manage.py collectstatic --noinput",
        "static": "No build required",
    }.get(project_type, "npm install && npm run build")


def _suggest_output_dir(project_type):
    return {"react": "dist", "node": "dist", "django": "staticfiles", "static": "."}.get(project_type, "dist")


def _project_from_deployment(deployment):
    name = deployment.upload.original_name.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title()[:160]
    domain = deployment.domain or f"{_vercel_project_name(name)}.vercel.app"
    project, _ = HostedProject.objects.get_or_create(
        domain=domain,
        defaults={
            "name": name,
            "client_name": "Upload Deployment",
            "hosting_platform": deployment.primary_provider,
            "deploy_url": f"https://{domain}",
            "status": HostedProject.Status.LIVE,
            "tag": "active",
            "expiry_date": timezone.localdate() + timedelta(days=365),
        },
    )
    deployment.upload.project = project
    deployment.upload.save(update_fields=["project"])
    return project
