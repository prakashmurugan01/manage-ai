import time
import base64
import json
import mimetypes
import os
import shutil
import socket
import ssl
import subprocess
import tempfile
import zipfile
from datetime import datetime, timedelta, timezone as dt_timezone
from pathlib import Path
from urllib.parse import quote, urlparse

from celery import shared_task
from django.conf import settings
from django.utils import timezone
import requests

from apps.notifications.tasks import check_hosting_expiry
from apps.projects.services import sync_project_deployment, sync_project_from_hosting
from apps.deployments.services import record_hosting_deployment

from .health import probe_url
from .models import DeploymentRun, DomainStatus, EmailAccount, HostedProject, HostingHealthCheck, HostingIncident, HostingLifecycle, HostingLink, ProjectUpload, VercelDeployment, VercelProjectLink
from .providers import failover_all_projects, sync_all_providers
from .vercel import VercelApiError, VercelClient, sync_vercel_projects


UPLOAD_DEPLOYMENT_ADAPTERS = {
    HostingLink.Provider.AWS: "_run_aws_s3_deployment",
    "azure": "_run_azure_app_service_deployment",
    "gcp": "_run_gcp_cloud_storage_deployment",
    HostingLink.Provider.CLOUDFLARE: "_run_cloudflare_pages_deployment",
    HostingLink.Provider.NETLIFY: "_run_netlify_deployment",
    HostingLink.Provider.VERCEL: "_run_vercel_deployment",
}


@shared_task(name="hosting.tasks.check_hosting_expiry")
def check_hosting_expiry_alias():
    return check_hosting_expiry.delay().id


@shared_task(name="hosting.tasks.check_hosted_project_health")
def check_hosted_project_health(project_id):
    project = HostedProject.objects.get(id=project_id)
    if project.status == HostedProject.Status.DISABLED or not project.link_is_active:
        project.server_status = HostedProject.ServerStatus.OFFLINE
        project.response_time_ms = 0
        project.last_checked_at = timezone.now()
        project.save(update_fields=["server_status", "response_time_ms", "last_checked_at"])
        return {"project_id": project.id, "server_status": project.server_status, "skipped": "disabled"}
    target = project.deploy_url or f"https://{project.domain}"
    result = probe_url(target, timeout=8, retries=2)
    status_value = _project_status_from_probe(result)
    status_code = result.status_code
    elapsed_ms = result.response_time_ms

    previous_status = project.server_status
    project.server_status = status_value
    project.response_time_ms = elapsed_ms
    project.last_checked_at = timezone.now()

    if status_value == HostedProject.ServerStatus.OFFLINE:
        project.downtime_count = project.downtime_count + 1
    else:
        project.downtime_count = 0
        project.link_is_active = True
        if project.status == HostedProject.Status.LIVE:
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
    check = _record_health_check(project, result, target_type=HostingHealthCheck.TargetType.PROJECT)
    _sync_incident_state(project, result, check=check)

    if status_value != previous_status:
        HostingLifecycle.objects.create(
            project=project,
            event_type=HostingLifecycle.Event.HEALTH_CHECK,
            notes=f"Health changed from {previous_status} to {status_value}. HTTP {status_code or 'n/a'}, {elapsed_ms}ms.",
        )
    sync_project_from_hosting(project)
    return {"project_id": project.id, "server_status": status_value, "http_status": status_code, "response_time_ms": elapsed_ms}


@shared_task(name="hosting.tasks.check_all_hosted_project_health")
def check_all_hosted_project_health():
    queued = 0
    eligible = HostedProject.objects.filter(archived_at__isnull=True).exclude(
        status__in=[HostedProject.Status.DISABLED, HostedProject.Status.EXPIRED, HostedProject.Status.SUSPENDED]
    )
    for project_id in eligible.values_list("id", flat=True):
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
        databases = _detect_databases(names)
        env_vars = _detect_environment_variables(names, project_type, databases)
        runtime_versions = _detect_runtime_versions(names, project_type)
        migration_command = _suggest_migration_command(project_type, databases)
        suggestions = _provider_suggestions(project_type)
        upload.detected_stack = stack
        upload.project_type = project_type
        upload.suggested_providers = suggestions
        upload.analysis = {
            "file_count": len(names),
            "entry_preview": names[:40],
            "build_command": _suggest_build_command(project_type),
            "start_command": _suggest_start_command(project_type),
            "output_directory": _suggest_output_dir(project_type),
            "environment_variables": env_vars,
            "databases": databases,
            "runtime_versions": runtime_versions,
            "migration_command": migration_command,
            "storage_required": _detect_storage_requirement(names),
            "ssl_required": True,
            "domain_required": True,
            "readiness_score": _readiness_score(project_type, names, env_vars),
            "deployment_options": _deployment_options(project_type, suggestions),
            "ci_cd": _ci_cd_template(project_type),
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
    deployment = DeploymentRun.objects.select_related("upload", "created_by", "project").get(id=deployment_id)
    _create_deployment_run_notification(deployment, "Deployment started", f"{deployment.upload.original_name} deployment started on {deployment.primary_provider}.", "info")
    try:
        return _run_selected_provider_deployment(deployment)
    except Exception as exc:
        _append_deployment_log(deployment, f"Deployment failed: {exc}", level="error")
        deployment.status = DeploymentRun.Status.FAILED
        deployment.error_message = str(exc)
        deployment.completed_at = timezone.now()
        deployment.save(update_fields=["status", "error_message", "completed_at", "logs"])
        if deployment.project_id:
            try:
                management_project = sync_project_deployment(deployment.project, deployment)
                record_hosting_deployment(deployment.project, deployment, management_project, status="FAILED")
            except Exception:
                pass
        _create_deployment_run_notification(deployment, "Deployment failed", f"{deployment.upload.original_name} failed on {deployment.primary_provider}: {exc}", "critical")
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
        sync_project_from_hosting(project)
        expired_count += 1
        archived_count += 1

    for project in HostedProject.objects.filter(archived_at__isnull=True, downtime_count__gte=3):
        if project.tag != "maintenance":
            project.tag = "maintenance"
            project.status = HostedProject.Status.MAINTENANCE
            project.save(update_fields=["tag", "status"])
            HostingLifecycle.objects.create(project=project, event_type=HostingLifecycle.Event.HEALTH_CHECK, notes="Flagged unstable after repeated downtime.")
            sync_project_from_hosting(project)
            unstable_count += 1
    return {"expired": expired_count, "archived": archived_count, "unstable": unstable_count}


def _next_uptime(current, status_value):
    current = float(current or 100)
    sample = 0 if status_value == HostedProject.ServerStatus.OFFLINE else 100
    return round((current * 19 + sample) / 20, 2)


def _project_status_from_probe(result):
    if not result.online:
        return HostedProject.ServerStatus.OFFLINE
    if result.slow:
        return HostedProject.ServerStatus.SLOW
    return HostedProject.ServerStatus.ONLINE


def _record_health_check(project, result, target_type, hosting_link=None, vercel_link=None):
    return HostingHealthCheck.objects.create(
        project=project,
        hosting_link=hosting_link,
        vercel_link=vercel_link,
        target_type=target_type,
        url=result.url,
        final_url=result.final_url or "",
        status_code=result.status_code,
        response_time_ms=result.response_time_ms,
        is_online=result.online,
        dns_ok=result.dns_ok,
        ssl_ok=result.ssl_ok,
        ssl_expires_at=result.ssl_expires_at,
        redirect_chain=result.redirect_chain,
        error_message=result.error,
    )


def _sync_incident_state(project, result, check=None, hosting_link=None, vercel_link=None):
    if result.online:
        incident = project.incidents.filter(status=HostingIncident.Status.OPEN, hosting_link=hosting_link, vercel_link=vercel_link).first()
        if incident:
            incident.status = HostingIncident.Status.RESOLVED
            incident.resolved_at = timezone.now()
            incident.downtime_seconds = max(0, int((incident.resolved_at - incident.started_at).total_seconds()))
            incident.last_status_code = result.status_code
            incident.last_error = ""
            incident.save(update_fields=["status", "resolved_at", "downtime_seconds", "last_status_code", "last_error"])
            HostingLifecycle.objects.create(
                project=project,
                event_type=HostingLifecycle.Event.INCIDENT_RESOLVED,
                notes=f"Recovered after {incident.downtime_seconds}s. HTTP {result.status_code or 'n/a'}, {result.response_time_ms}ms.",
            )
            _create_recovery_notification(project, incident)
        return None

    failures = _consecutive_failures(project, hosting_link=hosting_link, vercel_link=vercel_link)
    if failures < 3:
        return None
    incident, created = HostingIncident.objects.get_or_create(
        project=project,
        hosting_link=hosting_link,
        vercel_link=vercel_link,
        status=HostingIncident.Status.OPEN,
        defaults={
            "failure_count": failures,
            "last_status_code": result.status_code,
            "last_error": result.error,
            "metadata": {"first_check_id": check.id if check else None},
        },
    )
    if not created:
        incident.failure_count = failures
        incident.last_status_code = result.status_code
        incident.last_error = result.error
        incident.save(update_fields=["failure_count", "last_status_code", "last_error"])
        return incident
    HostingLifecycle.objects.create(
        project=project,
        event_type=HostingLifecycle.Event.INCIDENT_OPENED,
        notes=f"Incident opened after {failures} consecutive failed checks. HTTP {result.status_code or 'n/a'}, {result.response_time_ms}ms.",
    )
    _create_outage_notification(project, result.response_time_ms, failures=failures)
    return incident


def _consecutive_failures(project, hosting_link=None, vercel_link=None):
    checks = project.health_checks.all()
    if hosting_link is not None:
        checks = checks.filter(hosting_link=hosting_link)
    if vercel_link is not None:
        checks = checks.filter(vercel_link=vercel_link)
    count = 0
    for check in checks.order_by("-checked_at")[:6]:
        if check.is_online:
            break
        count += 1
    return count


def _create_outage_notification(project, elapsed_ms, failures=3):
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
        message=f"{project.domain} failed {failures} consecutive health checks. Last response: {elapsed_ms}ms. Hosting remains enabled while monitoring verifies recovery.",
    )
    _broadcast(notification)


def _create_recovery_notification(project, incident):
    from apps.notifications.models import Notification
    from apps.notifications.tasks import _broadcast, _notification_user

    user = _notification_user(project)
    if not user:
        return
    notification = Notification.objects.create(
        recipient=user,
        hosted_project=project,
        type=Notification.Type.SUCCESS,
        urgency="info",
        title=f"{project.name} recovered",
        message=f"{project.domain} is reachable again after {incident.downtime_seconds}s of monitored downtime.",
    )
    _broadcast(notification)


def _check_vercel_link(link):
    result = probe_url(link.url, timeout=8, retries=2)
    elapsed_ms = result.response_time_ms
    is_down = not result.online
    link.last_http_status = result.status_code
    link.response_time_ms = elapsed_ms
    link.last_checked_at = timezone.now()
    link.uptime_percentage = _next_uptime(link.uptime_percentage, HostedProject.ServerStatus.OFFLINE if is_down else HostedProject.ServerStatus.ONLINE)
    link.save(update_fields=["last_http_status", "response_time_ms", "last_checked_at", "uptime_percentage"])
    hosted_project = link.project.hosted_project
    if hosted_project:
        status_value = _project_status_from_probe(result)
        hosted_project.server_status = status_value
        hosted_project.downtime_count = hosted_project.downtime_count + 1 if is_down else 0
        hosted_project.last_checked_at = timezone.now()
        hosted_project.response_time_ms = elapsed_ms
        hosted_project.uptime_percentage = _next_uptime(hosted_project.uptime_percentage, status_value)
        if result.online:
            hosted_project.link_is_active = True
        hosted_project.save(update_fields=["server_status", "downtime_count", "last_checked_at", "response_time_ms", "uptime_percentage", "link_is_active"])
        check = _record_health_check(hosted_project, result, target_type=HostingHealthCheck.TargetType.VERCEL_LINK, vercel_link=link)
        _sync_incident_state(hosted_project, result, check=check, vercel_link=link)
        sync_project_from_hosting(hosted_project)


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


def _create_deployment_run_notification(deployment, title, message, urgency):
    from apps.notifications.services import notify_user

    recipient = deployment.created_by
    if not recipient and deployment.project:
        try:
            from apps.notifications.tasks import _notification_user

            recipient = _notification_user(deployment.project)
        except Exception:
            recipient = None
    if not recipient:
        return
    notify_user(
        recipient=recipient,
        sender=deployment.created_by if deployment.created_by_id != getattr(recipient, "id", None) else None,
        title=title,
        message=message,
        type="DEPLOYMENT",
        urgency=urgency,
        hosted_project=deployment.project,
    )


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


def _run_selected_provider_deployment(deployment):
    provider = str(deployment.primary_provider or "").lower()
    adapter_name = UPLOAD_DEPLOYMENT_ADAPTERS.get(provider)
    if not adapter_name:
        raise ValueError(
            f"{provider or 'selected provider'} is selected as the deployment target, "
            "but no uploaded-package deployment adapter is registered. No fallback provider was used."
        )
    adapter = globals().get(adapter_name)
    if not callable(adapter):
        raise ValueError(f"Deployment adapter '{adapter_name}' is not available for provider '{provider}'.")
    _append_deployment_log(deployment, f"Provider router selected {provider}. Fallback deployment is disabled.")
    return adapter(deployment)


def _run_aws_s3_deployment(deployment):
    bucket = _setting_first("AWS_DEPLOYMENT_BUCKET", "AWS_STORAGE_BUCKET_NAME")
    if not bucket:
        raise ValueError("AWS deployment requires AWS_DEPLOYMENT_BUCKET or AWS_STORAGE_BUCKET_NAME.")
    _ensure_settings(("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"))
    try:
        import boto3
    except ImportError as exc:
        raise ValueError("AWS deployment requires boto3 to be installed.") from exc

    project = deployment.project or _project_from_deployment(deployment)
    deployment.project = project
    deployment.save(update_fields=["project"])
    region = getattr(settings, "AWS_REGION", "us-east-1")
    prefix = _provider_project_slug(project.name or deployment.upload.original_name)
    session_kwargs = {
        "aws_access_key_id": getattr(settings, "AWS_ACCESS_KEY_ID", ""),
        "aws_secret_access_key": getattr(settings, "AWS_SECRET_ACCESS_KEY", ""),
        "region_name": region,
    }
    s3 = boto3.client("s3", **session_kwargs)
    _set_deployment_step(deployment, DeploymentRun.Status.UPLOADING, 18, f"Extracting package for AWS S3 deployment to {bucket}/{prefix}.")
    uploaded = 0
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        files_on_disk = _extract_upload_to_directory(deployment.upload, root)
        if not files_on_disk:
            raise ValueError("No deployable files found in the uploaded package.")
        for index, file_path in enumerate(files_on_disk, start=1):
            relative = file_path.relative_to(root).as_posix()
            key = f"{prefix}/{relative}".strip("/")
            content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
            s3.upload_file(str(file_path), bucket, key, ExtraArgs={"ContentType": content_type})
            uploaded += 1
            if index == 1 or index % 20 == 0 or index == len(files_on_disk):
                progress = 18 + int((index / len(files_on_disk)) * 58)
                _set_deployment_step(deployment, DeploymentRun.Status.DEPLOYING, progress, f"Uploaded {index}/{len(files_on_disk)} file(s) to AWS S3.")

    distribution_id = _setting_first("AWS_CLOUDFRONT_DISTRIBUTION_ID")
    if distribution_id:
        cloudfront = boto3.client("cloudfront", **session_kwargs)
        invalidation = cloudfront.create_invalidation(
            DistributionId=distribution_id,
            InvalidationBatch={
                "CallerReference": f"manageai-{deployment.id}-{int(time.time())}",
                "Paths": {"Quantity": 1, "Items": [f"/{prefix}/*"]},
            },
        )
        deployment.build_id = invalidation.get("Invalidation", {}).get("Id", "")
        _append_deployment_log(deployment, f"CloudFront invalidation queued: {deployment.build_id}.")

    live_url = _absolute_url(deployment.domain or _setting_first("AWS_DEPLOYMENT_URL") or f"{bucket}.s3-website-{region}.amazonaws.com/{prefix}/")
    deployment.provider_deployment_id = f"s3://{bucket}/{prefix}"
    _finalize_provider_deployment(deployment, project, live_url, HostingLink.Provider.AWS, {"bucket": bucket, "prefix": prefix, "uploaded_files": uploaded})
    return {"deployment_id": str(deployment.id), "status": deployment.status, "live_url": live_url, "provider_deployment_id": deployment.provider_deployment_id}


def _run_netlify_deployment(deployment):
    token = _setting_first("NETLIFY_TOKEN", "NETLIFY_API_TOKEN")
    site_id = _setting_first("NETLIFY_SITE_ID")
    if not token:
        raise ValueError("Netlify deployment requires NETLIFY_TOKEN or NETLIFY_API_TOKEN.")
    if not site_id:
        raise ValueError("Netlify deployment requires NETLIFY_SITE_ID.")
    project = deployment.project or _project_from_deployment(deployment)
    deployment.project = project
    deployment.save(update_fields=["project"])
    _set_deployment_step(deployment, DeploymentRun.Status.UPLOADING, 18, f"Preparing ZIP package for Netlify site {site_id}.")
    zip_path = _zip_upload_for_provider(deployment)
    with open(zip_path, "rb") as package:
        response = requests.post(
            f"https://api.netlify.com/api/v1/sites/{site_id}/deploys",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/zip"},
            data=package,
            timeout=60,
        )
    payload = _provider_json_response(response, "Netlify deployment creation failed.")
    provider_id = str(payload.get("id") or payload.get("deploy_id") or "")
    if not provider_id:
        raise ValueError("Netlify API did not return a deployment id.")
    deployment.provider_deployment_id = provider_id
    deployment.build_id = str(payload.get("build_id") or "")
    _set_deployment_step(deployment, DeploymentRun.Status.BUILDING, 72, f"Netlify deployment created: {provider_id}. Waiting for readiness.")
    latest = payload
    for _ in range(20):
        state = str(latest.get("state") or latest.get("deploy_state") or "").lower()
        if state in {"ready", "uploaded"}:
            break
        if state in {"error", "failed", "rejected"}:
            raise ValueError(latest.get("error_message") or f"Netlify deployment ended with {state}.")
        time.sleep(3)
        status_response = requests.get(f"https://api.netlify.com/api/v1/deploys/{provider_id}", headers={"Authorization": f"Bearer {token}"}, timeout=30)
        latest = _provider_json_response(status_response, "Netlify deployment status failed.")
    live_url = _absolute_url(deployment.domain or latest.get("ssl_url") or latest.get("url") or latest.get("deploy_ssl_url") or latest.get("deploy_url") or "")
    if not live_url:
        raise ValueError("Netlify API did not return a live URL.")
    _finalize_provider_deployment(deployment, project, live_url, HostingLink.Provider.NETLIFY, latest)
    return {"deployment_id": str(deployment.id), "status": deployment.status, "live_url": live_url, "provider_deployment_id": provider_id}


def _run_azure_app_service_deployment(deployment):
    _ensure_settings(("AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "AZURE_TENANT_ID", "AZURE_SUBSCRIPTION_ID", "AZURE_RESOURCE_GROUP", "AZURE_APP_SERVICE_NAME"))
    app_name = _setting_first("AZURE_APP_SERVICE_NAME")
    project = deployment.project or _project_from_deployment(deployment)
    deployment.project = project
    deployment.save(update_fields=["project"])

    _set_deployment_step(deployment, DeploymentRun.Status.UPLOADING, 18, f"Preparing ZIP package for Azure App Service {app_name}.")
    zip_path = _zip_upload_for_provider(deployment)
    token = _azure_access_token()
    publish_url = _setting_first("AZURE_KUDU_PUBLISH_URL") or f"https://{app_name}.scm.azurewebsites.net/api/publish?type=zip"
    with open(zip_path, "rb") as package:
        response = requests.post(
            publish_url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/zip"},
            data=package,
            timeout=180,
        )
    if response.status_code >= 400:
        raise ValueError(_provider_error_text(response, "Azure App Service ZIP deployment failed."))

    _set_deployment_step(deployment, DeploymentRun.Status.BUILDING, 72, "Azure App Service accepted the ZIP package. Reading provider deployment record.")
    latest = _azure_app_service_latest_deployment(app_name, token)
    provider_id = str(latest.get("id") or latest.get("deploymentId") or latest.get("message") or "")
    if not provider_id:
        raise ValueError("Azure App Service did not return a deployment id from Kudu.")
    deployment.provider_deployment_id = provider_id
    deployment.build_id = str(latest.get("build_summary", {}).get("id") or latest.get("active") or "")
    live_url = _absolute_url(deployment.domain or _setting_first("AZURE_APP_SERVICE_URL") or f"{app_name}.azurewebsites.net")
    _finalize_provider_deployment(deployment, project, live_url, "azure", latest)
    return {"deployment_id": str(deployment.id), "status": deployment.status, "live_url": live_url, "provider_deployment_id": provider_id}


def _run_gcp_cloud_storage_deployment(deployment):
    _ensure_settings(("GCP_PROJECT_ID", "GCP_STORAGE_BUCKET"))
    bucket = _setting_first("GCP_STORAGE_BUCKET")
    token = _gcp_access_token()
    project = deployment.project or _project_from_deployment(deployment)
    deployment.project = project
    deployment.save(update_fields=["project"])

    prefix = _provider_project_slug(project.name or deployment.upload.original_name)
    _set_deployment_step(deployment, DeploymentRun.Status.UPLOADING, 18, f"Extracting package for Google Cloud Storage deployment to gs://{bucket}/{prefix}.")
    uploaded = 0
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        files_on_disk = _extract_upload_to_directory(deployment.upload, root)
        deploy_root = _select_deploy_root(root, deployment)
        files_on_disk = [path for path in files_on_disk if path == deploy_root or deploy_root in path.parents]
        if not files_on_disk:
            raise ValueError("No deployable files found in the selected Google Cloud output directory.")
        for index, file_path in enumerate(files_on_disk, start=1):
            relative = file_path.relative_to(deploy_root).as_posix()
            key = f"{prefix}/{relative}".strip("/")
            content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
            with open(file_path, "rb") as source:
                response = requests.post(
                    f"https://storage.googleapis.com/upload/storage/v1/b/{quote(bucket, safe='')}/o",
                    params={"uploadType": "media", "name": key},
                    headers={"Authorization": f"Bearer {token}", "Content-Type": content_type},
                    data=source,
                    timeout=90,
                )
            _provider_json_response(response, "Google Cloud Storage object upload failed.")
            uploaded += 1
            if index == 1 or index % 20 == 0 or index == len(files_on_disk):
                progress = 18 + int((index / len(files_on_disk)) * 58)
                _set_deployment_step(deployment, DeploymentRun.Status.DEPLOYING, progress, f"Uploaded {index}/{len(files_on_disk)} file(s) to Google Cloud Storage.")

    live_url = _absolute_url(deployment.domain or _setting_first("GCP_DEPLOYMENT_URL") or f"storage.googleapis.com/{bucket}/{prefix}/index.html")
    deployment.provider_deployment_id = f"gs://{bucket}/{prefix}"
    _finalize_provider_deployment(deployment, project, live_url, "gcp", {"bucket": bucket, "prefix": prefix, "uploaded_files": uploaded})
    return {"deployment_id": str(deployment.id), "status": deployment.status, "live_url": live_url, "provider_deployment_id": deployment.provider_deployment_id}


def _run_cloudflare_pages_deployment(deployment):
    _ensure_settings(("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_PAGES_PROJECT_NAME"))
    account_id = _setting_first("CLOUDFLARE_ACCOUNT_ID")
    project_name = _setting_first("CLOUDFLARE_PAGES_PROJECT_NAME")
    branch = _setting_first("CLOUDFLARE_PAGES_BRANCH") or "main"
    project = deployment.project or _project_from_deployment(deployment)
    deployment.project = project
    deployment.save(update_fields=["project"])

    _set_deployment_step(deployment, DeploymentRun.Status.UPLOADING, 18, f"Extracting package for Cloudflare Pages project {project_name}.")
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        files_on_disk = _extract_upload_to_directory(deployment.upload, root)
        deploy_root = _select_deploy_root(root, deployment)
        if not any(path == deploy_root or deploy_root in path.parents for path in files_on_disk):
            raise ValueError("No deployable files found in the selected Cloudflare Pages output directory.")
        command = _cli_command(
            setting_name="CLOUDFLARE_WRANGLER_BIN",
            default_binary="npx --yes",
            npx_package="wrangler",
            args=[
                "pages",
                "deploy",
                str(deploy_root),
                "--project-name",
                project_name,
                "--branch",
                branch,
                "--commit-dirty=true",
            ],
        )
        env = {**os.environ, "CLOUDFLARE_API_TOKEN": _setting_first("CLOUDFLARE_API_TOKEN"), "CLOUDFLARE_ACCOUNT_ID": account_id}
        _set_deployment_step(deployment, DeploymentRun.Status.DEPLOYING, 58, "Calling Cloudflare Wrangler for a real Pages direct upload.")
        output = _run_command_capture(command, cwd=deploy_root, env=env, timeout=300)
        for line in output[-8:]:
            _append_deployment_log(deployment, f"Cloudflare: {line}")

    _set_deployment_step(deployment, DeploymentRun.Status.BUILDING, 82, "Reading Cloudflare Pages deployment record.")
    payload = _cloudflare_get(
        f"https://api.cloudflare.com/client/v4/accounts/{account_id}/pages/projects/{project_name}/deployments",
        params={"env": "production", "per_page": 1},
    )
    deployments = payload.get("result") or []
    if not deployments:
        raise ValueError("Cloudflare Pages deployment completed but no provider deployment record was returned.")
    latest = deployments[0]
    provider_id = str(latest.get("id") or latest.get("short_id") or "")
    if not provider_id:
        raise ValueError("Cloudflare Pages API did not return a deployment id.")
    live_url = _absolute_url(deployment.domain or latest.get("url") or _parse_first_url("\n".join(output)) or "")
    if not live_url:
        raise ValueError("Cloudflare Pages API did not return a live URL.")
    deployment.provider_deployment_id = provider_id
    deployment.build_id = str(latest.get("short_id") or "")
    _finalize_provider_deployment(deployment, project, live_url, HostingLink.Provider.CLOUDFLARE, latest)
    return {"deployment_id": str(deployment.id), "status": deployment.status, "live_url": live_url, "provider_deployment_id": provider_id}


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

    live_url = _absolute_url(latest.get("url") or deployment_url or "")
    if not live_url:
        raise ValueError("Vercel API did not return a deployment URL.")
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
    deployment.provider_deployment_id = str(vercel_id or "")
    deployment.build_id = str(latest.get("buildId") or latest.get("build_id") or "")
    _finalize_provider_deployment(deployment, project, final_url, HostingLink.Provider.VERCEL, latest)
    return {"deployment_id": str(deployment.id), "status": deployment.status, "live_url": final_url, "vercel_id": vercel_id}


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
    if parts.intersection({"node_modules", ".git", "__pycache__", ".venv", "venv"}):
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


def _finalize_provider_deployment(deployment, project, live_url, provider, raw):
    _set_deployment_step(deployment, DeploymentRun.Status.VERIFYING, 90, f"Verifying live URL for {provider}: {live_url}.")
    probe = probe_url(live_url, timeout=10, retries=2) if live_url else None
    final_domain = urlparse(live_url).netloc or project.domain
    if final_domain and project.domain != final_domain and not HostedProject.objects.filter(domain=final_domain).exclude(id=project.id).exists():
        project.domain = final_domain
    project.deploy_url = live_url
    project.hosting_platform = provider
    project.status = HostedProject.Status.LIVE
    project.tag = "active"
    project.link_is_active = True
    project.server_status = _project_status_from_probe(probe) if probe else HostedProject.ServerStatus.UNKNOWN
    project.response_time_ms = probe.response_time_ms if probe else 0
    project.last_checked_at = timezone.now()
    project.save(update_fields=["domain", "deploy_url", "hosting_platform", "status", "tag", "link_is_active", "server_status", "response_time_ms", "last_checked_at"])
    deployment.live_url = live_url
    deployment.status = DeploymentRun.Status.LIVE
    deployment.progress = 100
    deployment.metrics = _metrics_from_probe(probe)
    deployment.completed_at = timezone.now()
    deployment.save(update_fields=["provider_deployment_id", "build_id", "live_url", "status", "progress", "metrics", "completed_at", "logs"])
    _append_deployment_log(deployment, f"{provider} deployment is live: {live_url}")
    _upsert_deployment_link(project, deployment, live_url, provider, raw)
    management_project = sync_project_deployment(project, deployment)
    record_hosting_deployment(project, deployment, management_project, status="SUCCESS")
    _create_deployment_run_notification(deployment, "Deployment successful", f"{project.name} is live at {live_url}.", "info")


def _metrics_from_probe(result):
    if not result:
        return {}
    return {
        "latency_ms": result.response_time_ms,
        "response_time_ms": result.response_time_ms,
        "health": "healthy" if result.online else "down",
        "http_status": result.status_code,
        "dns_ok": result.dns_ok,
        "ssl_ok": result.ssl_ok,
    }


def _setting_first(*names):
    for name in names:
        value = getattr(settings, name, "")
        if str(value or "").strip():
            return str(value).strip()
    return ""


def _ensure_settings(names):
    missing = [name for name in names if not _setting_first(name)]
    if missing:
        raise ValueError(f"Missing required provider setting(s): {', '.join(missing)}.")


def _azure_access_token():
    response = requests.post(
        f"https://login.microsoftonline.com/{_setting_first('AZURE_TENANT_ID')}/oauth2/v2.0/token",
        data={
            "client_id": _setting_first("AZURE_CLIENT_ID"),
            "client_secret": _setting_first("AZURE_CLIENT_SECRET"),
            "grant_type": "client_credentials",
            "scope": "https://management.azure.com/.default",
        },
        timeout=30,
    )
    payload = _provider_json_response(response, "Azure Entra token request failed.")
    token = payload.get("access_token")
    if not token:
        raise ValueError("Azure Entra token response did not include access_token.")
    return token


def _azure_app_service_latest_deployment(app_name, token):
    latest_url = f"https://{app_name}.scm.azurewebsites.net/api/deployments/latest"
    for _ in range(12):
        response = requests.get(latest_url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
        if response.status_code < 400:
            payload = _provider_json_response(response, "Azure App Service deployment status failed.")
            status_value = str(payload.get("status") or payload.get("complete") or "").lower()
            if status_value in {"4", "true", "success"} or payload.get("complete") is True:
                return payload
            if status_value in {"3", "failed", "failure"} or payload.get("status") == 3:
                raise ValueError(payload.get("message") or "Azure App Service deployment failed.")
        time.sleep(3)
    response = requests.get(latest_url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
    return _provider_json_response(response, "Azure App Service deployment status failed.")


def _gcp_access_token():
    direct_token = _setting_first("GCP_ACCESS_TOKEN")
    if direct_token:
        return direct_token
    info = _gcp_service_account_info()
    now = int(time.time())
    header = {"alg": "RS256", "typ": "JWT"}
    claims = {
        "iss": info["client_email"],
        "scope": "https://www.googleapis.com/auth/devstorage.read_write",
        "aud": "https://oauth2.googleapis.com/token",
        "iat": now,
        "exp": now + 3600,
    }
    assertion = _sign_google_jwt(header, claims, info["private_key"])
    response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion},
        timeout=30,
    )
    payload = _provider_json_response(response, "Google OAuth token request failed.")
    token = payload.get("access_token")
    if not token:
        raise ValueError("Google OAuth token response did not include access_token.")
    return token


def _gcp_service_account_info():
    raw_json = _setting_first("GCP_SERVICE_ACCOUNT_JSON")
    credential_path = _setting_first("GOOGLE_APPLICATION_CREDENTIALS")
    if raw_json:
        if raw_json.lstrip().startswith("{"):
            info = json.loads(raw_json)
        else:
            info = json.loads(Path(raw_json).read_text(encoding="utf-8"))
    elif credential_path:
        info = json.loads(Path(credential_path).read_text(encoding="utf-8"))
    else:
        raise ValueError("Google Cloud deployment requires GCP_ACCESS_TOKEN, GCP_SERVICE_ACCOUNT_JSON, or GOOGLE_APPLICATION_CREDENTIALS.")
    if not info.get("client_email") or not info.get("private_key"):
        raise ValueError("Google service account credentials must include client_email and private_key.")
    return info


def _sign_google_jwt(header, claims, private_key):
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    def encode(value):
        raw = json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    signing_input = f"{encode(header)}.{encode(claims)}".encode("ascii")
    key = serialization.load_pem_private_key(private_key.encode("utf-8"), password=None)
    signature = key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return f"{signing_input.decode('ascii')}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode('ascii')}"


def _cloudflare_get(url, params=None):
    response = requests.get(
        url,
        params=params,
        headers={"Authorization": f"Bearer {_setting_first('CLOUDFLARE_API_TOKEN')}"},
        timeout=30,
    )
    return _provider_json_response(response, "Cloudflare API request failed.")


def _cli_command(setting_name, default_binary, npx_package, args):
    configured = _setting_first(setting_name) or default_binary
    parts = configured.split()
    executable = parts[0]
    if shutil.which(executable) is None:
        raise ValueError(f"Required CLI '{executable}' was not found on PATH for {setting_name}.")
    if executable.lower().endswith("npx") or Path(executable).name.lower() in {"npx", "npx.cmd"}:
        return parts + [npx_package] + args
    return parts + args


def _run_command_capture(command, cwd, env, timeout):
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    output = [line.strip() for line in (completed.stdout or "").splitlines() if line.strip()]
    errors = [line.strip() for line in (completed.stderr or "").splitlines() if line.strip()]
    if completed.returncode != 0:
        detail = "\n".join((errors or output)[-8:]) or f"Command exited with code {completed.returncode}."
        raise ValueError(detail)
    return output + errors


def _parse_first_url(value):
    for token in str(value or "").replace("\r", "\n").split():
        cleaned = token.strip(".,;()[]{}<>\"'")
        if cleaned.startswith(("https://", "http://")):
            return cleaned
    return ""


def _provider_project_slug(value):
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in str(value or "manageai-upload"))
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return (cleaned or "manageai-upload")[:80]


def _select_deploy_root(root, deployment):
    explicit = str(deployment.output_directory or "").strip().strip("/\\")
    analysis = deployment.upload.analysis if isinstance(deployment.upload.analysis, dict) else {}
    candidates = [explicit]
    if not explicit:
        candidates.extend([str(analysis.get("output_directory") or "").strip().strip("/\\"), "dist", "build", "out", "public"])
    for candidate_name in [name for name in candidates if name and name not in {".", "/"}]:
        candidate = (root / candidate_name).resolve()
        root_resolved = root.resolve()
        if root_resolved not in candidate.parents and candidate != root_resolved:
            raise ValueError(f"Output directory escapes project root: {candidate_name}.")
        if candidate.exists() and candidate.is_dir():
            return candidate
        if explicit:
            raise ValueError(f"Configured output directory '{explicit}' was not found in the uploaded package.")
    return root


def _zip_upload_for_provider(deployment):
    archive_path = Path(tempfile.gettempdir()) / f"manageai-deployment-{deployment.id}.zip"
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        files = _extract_upload_to_directory(deployment.upload, root)
        deploy_root = _select_deploy_root(root, deployment)
        files = [path for path in files if path == deploy_root or deploy_root in path.parents]
        if not files:
            raise ValueError("No deployable files found in the selected output directory.")
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for file_path in files:
                archive.write(file_path, file_path.relative_to(deploy_root).as_posix())
    return archive_path


def _provider_error_text(response, fallback):
    try:
        payload = response.json() if response.content else {}
    except ValueError:
        payload = {}
    if isinstance(payload, dict):
        return payload.get("message") or payload.get("error") or payload.get("detail") or response.text or fallback
    return response.text or fallback


def _provider_json_response(response, fallback):
    try:
        payload = response.json() if response.content else {}
    except ValueError:
        payload = {"detail": response.text}
    if response.status_code >= 400:
        message = payload.get("message") or payload.get("error") or payload.get("detail") or response.text or fallback
        raise ValueError(message)
    return payload


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
    return {"react": "vite", "next": "nextjs", "vue": "vue", "angular": "angular", "node": None, "static": None, "django": None, "flask": None, "laravel": None}.get(project_type)


def _uploaded_file_names(upload):
    path = upload.upload.path
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            return [item.filename for item in archive.infolist() if not item.is_dir()]
    return [upload.original_name]


def _detect_stack(names):
    lowered = [name.lower() for name in names]
    joined = " ".join(lowered)
    stack = []
    if any(name.endswith("package.json") for name in lowered):
        stack.append("Node.js")
    if any("vite.config" in name or "src/app.jsx" in name or "src/main.jsx" in name for name in lowered):
        stack.append("React")
    if any(name.endswith("angular.json") for name in lowered):
        stack.append("Angular")
    if any(name.endswith("vue.config.js") or "src/main.js" in name and "package.json" in lowered for name in lowered):
        stack.append("Vue")
    if any(name.endswith("manage.py") for name in lowered):
        stack.append("Django")
    if any(name.endswith(("requirements.txt", "pyproject.toml", "pipfile")) for name in lowered):
        stack.append("Python")
    if "fastapi" in joined or any(name.endswith(("main.py", "app/main.py", "src/main.py")) for name in lowered):
        stack.append("FastAPI")
    if any(name.endswith("artisan") or name.endswith("composer.json") for name in lowered):
        stack.append("Laravel")
    if any(name.endswith("app.py") or name.endswith("wsgi.py") for name in lowered):
        stack.append("Flask")
    if any(name.endswith("next.config.js") for name in lowered):
        stack.append("Next.js")
    if any(name.endswith(("pom.xml", "build.gradle", "build.gradle.kts")) for name in lowered):
        stack.append("Spring Boot")
    if any(name.endswith((".csproj", ".fsproj", ".vbproj", ".sln")) for name in lowered):
        stack.append(".NET")
    if any(name.endswith("firebase.json") for name in lowered):
        stack.append("Firebase")
    if any(name.endswith("dockerfile") or name.endswith("docker-compose.yml") or name.endswith("docker-compose.yaml") for name in lowered):
        stack.append("Docker")
    if any(name.endswith("index.html") for name in lowered) and not stack:
        stack.append("Static")
    if "Django" in stack:
        return stack, "django"
    if "Laravel" in stack:
        return stack, "laravel"
    if "FastAPI" in stack:
        return stack, "fastapi"
    if "Next.js" in stack:
        return stack, "next"
    if "React" in stack:
        return stack, "react"
    if "Angular" in stack:
        return stack, "angular"
    if "Vue" in stack:
        return stack, "vue"
    if "Flask" in stack:
        return stack, "flask"
    if "Firebase" in stack:
        return stack, "firebase"
    if "Spring Boot" in stack:
        return stack, "spring_boot"
    if ".NET" in stack:
        return stack, "dotnet"
    if "Node.js" in stack:
        return stack, "node"
    if "Static" in stack:
        return stack, "static"
    return stack or ["Unknown"], "static"


def _provider_suggestions(project_type):
    return {
        "react": ["vercel", "netlify", "cloudflare"],
        "next": ["vercel", "netlify", "render"],
        "vue": ["netlify", "vercel", "cloudflare"],
        "angular": ["netlify", "vercel", "firebase"],
        "node": ["railway", "render", "digitalocean"],
        "django": ["aws", "digitalocean", "cloudways"],
        "fastapi": ["fly", "railway", "render"],
        "flask": ["render", "railway", "digitalocean"],
        "laravel": ["digitalocean", "cpanel", "hostinger"],
        "spring_boot": ["aws", "azure", "gcp"],
        "dotnet": ["azure", "aws", "gcp"],
        "firebase": ["firebase", "vercel", "netlify"],
        "static": ["netlify", "vercel", "aws_s3"],
    }.get(project_type, ["aws", "digitalocean"])


def _suggest_build_command(project_type):
    return {
        "react": "npm install && npm run build",
        "next": "npm install && npm run build",
        "vue": "npm install && npm run build",
        "angular": "npm install && npm run build",
        "node": "npm install && npm run build",
        "django": "pip install -r requirements.txt && python manage.py collectstatic --noinput",
        "fastapi": "pip install -r requirements.txt",
        "flask": "pip install -r requirements.txt",
        "laravel": "composer install --no-dev --optimize-autoloader && npm install && npm run build",
        "spring_boot": "./mvnw package -DskipTests || mvn package -DskipTests",
        "dotnet": "dotnet publish -c Release",
        "firebase": "npm install && npm run build",
        "static": "No build required",
    }.get(project_type, "npm install && npm run build")


def _suggest_output_dir(project_type):
    return {
        "react": "dist",
        "next": ".next",
        "vue": "dist",
        "angular": "dist",
        "node": "dist",
        "django": "staticfiles",
        "fastapi": "public",
        "flask": "public",
        "laravel": "public",
        "spring_boot": "target",
        "dotnet": "bin/Release",
        "firebase": "dist",
        "static": ".",
    }.get(project_type, "dist")


def _suggest_start_command(project_type):
    return {
        "react": "npm run preview",
        "next": "npm start",
        "vue": "npm run preview",
        "angular": "npx serve dist",
        "node": "npm start",
        "django": "gunicorn project.wsgi:application",
        "fastapi": "uvicorn main:app --host 0.0.0.0 --port $PORT",
        "flask": "gunicorn app:app",
        "laravel": "php artisan serve --host=0.0.0.0",
        "spring_boot": "java -jar target/app.jar",
        "dotnet": "dotnet app.dll",
        "firebase": "firebase deploy",
        "static": "npx serve .",
    }.get(project_type, "npm start")


def _detect_databases(names):
    lowered = " ".join(name.lower() for name in names)
    databases = []
    checks = [
        ("PostgreSQL", ["postgres", "postgresql", "psycopg", "pgvector", "DATABASE_URL"]),
        ("MySQL", ["mysql", "pymysql", "mysqlclient"]),
        ("MongoDB", ["mongodb", "mongoose", "pymongo"]),
        ("MariaDB", ["mariadb"]),
        ("SQLite", ["sqlite", "db.sqlite3"]),
        ("Redis", ["redis", "celery", "rq"]),
        ("Firebase", ["firebase.json", "firestore", "firebase"]),
    ]
    for label, tokens in checks:
        if any(token.lower() in lowered for token in tokens):
            databases.append(label)
    return databases or ["None detected"]


def _detect_environment_variables(names, project_type, databases):
    variables = {"NODE_ENV" if project_type in {"react", "next", "vue", "angular", "node", "firebase"} else "ENVIRONMENT"}
    lowered = " ".join(name.lower() for name in names)
    if any(db in databases for db in ["PostgreSQL", "MySQL", "MariaDB", "MongoDB"]):
        variables.add("DATABASE_URL")
    if "Redis" in databases:
        variables.add("REDIS_URL")
    if "Firebase" in databases or project_type == "firebase":
        variables.update({"FIREBASE_PROJECT_ID", "FIREBASE_SERVICE_ACCOUNT"})
    if any(".env" in name.lower() for name in names):
        variables.add("SECRET_KEY")
    if "django" in project_type:
        variables.update({"DJANGO_SETTINGS_MODULE", "ALLOWED_HOSTS"})
    if "laravel" in project_type:
        variables.update({"APP_KEY", "APP_ENV"})
    if "stripe" in lowered:
        variables.add("STRIPE_SECRET_KEY")
    if "s3" in lowered or "storage" in lowered:
        variables.update({"AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_STORAGE_BUCKET_NAME"})
    return sorted(variables)


def _detect_runtime_versions(names, project_type):
    lowered = [name.lower() for name in names]
    versions = {}
    if project_type in {"react", "next", "vue", "angular", "node", "firebase"} or any(name.endswith("package.json") for name in lowered):
        versions["node"] = "18+"
    if project_type in {"django", "flask", "fastapi"} or any(name.endswith("requirements.txt") or name.endswith("pyproject.toml") for name in lowered):
        versions["python"] = "3.10+"
    if project_type == "laravel" or any(name.endswith("composer.json") for name in lowered):
        versions["php"] = "8.1+"
    if project_type == "spring_boot" or any(name.endswith(("pom.xml", "build.gradle", "build.gradle.kts")) for name in lowered):
        versions["java"] = "17+"
    if project_type == "dotnet" or any(name.endswith((".csproj", ".sln")) for name in lowered):
        versions["dotnet"] = "8.0+"
    return versions


def _suggest_migration_command(project_type, databases):
    if project_type == "django" and databases != ["None detected"]:
        return "python manage.py migrate --noinput"
    if project_type == "laravel" and databases != ["None detected"]:
        return "php artisan migrate --force"
    if project_type in {"node", "next"} and databases != ["None detected"]:
        return "npm run migrate --if-present"
    if project_type == "dotnet" and databases != ["None detected"]:
        return "dotnet ef database update"
    return ""


def _detect_storage_requirement(names):
    lowered = " ".join(name.lower() for name in names)
    return any(token in lowered for token in ["media/", "uploads/", "storage/", "s3", "cloudinary", "multer"])


def _readiness_score(project_type, names, env_vars):
    score = 70
    lowered = [name.lower() for name in names]
    if project_type != "static":
        score += 8
    if any(name.endswith(("package.json", "requirements.txt", "composer.json", "pyproject.toml")) for name in lowered):
        score += 8
    if any("dockerfile" in name or "vercel.json" in name or "netlify.toml" in name for name in lowered):
        score += 6
    if env_vars:
        score += 4
    if any(name.endswith((".env.example", ".env.sample")) for name in lowered):
        score += 4
    return min(score, 99)


def _deployment_options(project_type, providers):
    return {
        "primary_provider": providers[0] if providers else "",
        "backup_provider": providers[1] if len(providers) > 1 else "",
        "ssl": "automatic",
        "domain": "auto-link custom domain when provided",
        "autoscaling": project_type in {"next", "node", "django", "flask", "fastapi", "spring_boot", "dotnet"},
        "health_check_path": "/api/health" if project_type in {"next", "node"} else "/health",
        "rollback": "previous deployment run",
    }


def _ci_cd_template(project_type):
    return {
        "provider": "github_actions",
        "trigger": "push to main",
        "build": _suggest_build_command(project_type),
        "migrate": _suggest_migration_command(project_type, ["database"]),
        "deploy": "manageai deployment adapter",
    }


def _project_from_deployment(deployment):
    name = deployment.upload.original_name.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title()[:160]
    domain = deployment.domain or _generated_domain_for_provider(deployment.primary_provider, name)
    project, _ = HostedProject.objects.get_or_create(
        domain=domain,
        defaults={
            "name": name,
            "client_name": "Upload Deployment",
            "hosting_platform": deployment.primary_provider,
            "deploy_url": "",
            "status": HostedProject.Status.PENDING,
            "tag": "deployment",
            "expiry_date": timezone.localdate() + timedelta(days=365),
        },
    )
    deployment.upload.project = project
    deployment.upload.save(update_fields=["project"])
    return project


def _generated_domain_for_provider(provider, name):
    slug = _provider_project_slug(name)
    suffixes = {
        "aws": "pending.aws.manageai.local",
        "azure": "pending.azure.manageai.local",
        "gcp": "pending.gcp.manageai.local",
        "netlify": "pending.netlify.manageai.local",
        "cloudflare": "pending.cloudflare.manageai.local",
        "vercel": "pending.vercel.manageai.local",
    }
    return f"{slug}.{suffixes.get(str(provider or '').lower(), 'pending.manageai.local')}"
