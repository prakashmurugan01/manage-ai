from decimal import Decimal
from pathlib import Path

from django.db import transaction

from .models import DeploymentControl, DeploymentRecord


CONFIG_FILE_NAMES = {
    ".env",
    ".env.example",
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "nginx.conf",
    "vercel.json",
    "netlify.toml",
    "package.json",
    "requirements.txt",
    "pyproject.toml",
    "vite.config.js",
    "vite.config.ts",
    "next.config.js",
    "next.config.mjs",
}


def record_hosting_deployment(hosted_project, deployment, project, status=None):
    assigned_developer = _assigned_developer(project, deployment)
    deployment_status = status or _record_status(getattr(deployment, "status", ""))
    server_details = {
        "server_ip": str(hosted_project.server_ip or ""),
        "server_status": hosted_project.server_status,
        "response_time_ms": hosted_project.response_time_ms,
        "hosting_platform": hosted_project.hosting_platform,
        "deploy_url": hosted_project.deploy_url,
    }
    deployment_at = deployment.completed_at or deployment.created_at
    uploaded_names = _uploaded_names(deployment)
    pdf_documents = _project_pdf_documents(project)
    configuration_files = _configuration_files(uploaded_names)

    with transaction.atomic():
        record, _ = DeploymentRecord.objects.update_or_create(
            hosting_deployment=deployment,
            defaults={
                "project": project,
                "hosted_project": hosted_project,
                "project_name": hosted_project.name or project.name,
                "external_project_id": str(hosted_project.id),
                "client_name": hosted_project.display_client_name or "",
                "assigned_developer": assigned_developer,
                "assigned_developer_name": assigned_developer.get_full_name() or assigned_developer.email if assigned_developer else "",
                "deployment_at": deployment_at,
                "hosting_provider": deployment.primary_provider or hosted_project.hosting_platform,
                "domain": hosted_project.domain,
                "live_url": deployment.live_url or hosted_project.deploy_url,
                "server_details": server_details,
                "cost": hosted_project.monthly_cost or Decimal("0"),
                "renewal_cost": hosted_project.monthly_cost or Decimal("0"),
                "expiry_date": hosted_project.expiry_date,
                "status": deployment_status,
                "deployment_logs": deployment.logs or [],
                "pdf_documents": pdf_documents,
                "configuration_files": configuration_files,
                "notes": hosted_project.notes or "",
                "created_by": deployment.created_by,
            },
        )
        control, _ = DeploymentControl.objects.get_or_create(project=project, defaults={"environment": DeploymentControl.Environment.PRODUCTION})
        control.is_enabled = deployment_status == DeploymentRecord.Status.SUCCESS
        control.status = DeploymentControl.Status.HEALTHY if control.is_enabled else DeploymentControl.Status.FAILED
        control.version = str(deployment.id)[:80]
        control.source_branch = ""
        control.commit_sha = ""
        control.last_deployed_at = deployment_at if control.is_enabled else control.last_deployed_at
        control.toggled_by = deployment.created_by
        control.notes = f"{deployment.primary_provider} deployment {deployment_status.lower()}"
        control.save()
    return record


def _record_status(status):
    normalized = str(status or "").lower()
    if normalized in {"live", "success", "ready", "deployed"}:
        return DeploymentRecord.Status.SUCCESS
    if normalized in {"error", "failed", "canceled"}:
        return DeploymentRecord.Status.FAILED
    if normalized in {"queued"}:
        return DeploymentRecord.Status.QUEUED
    return DeploymentRecord.Status.RUNNING


def _assigned_developer(project, deployment):
    user = getattr(deployment, "created_by", None)
    if user and getattr(user, "role", "") == "DEVELOPER":
        return user
    return project.developers.order_by("id").first()


def _uploaded_names(deployment):
    upload = getattr(deployment, "upload", None)
    analysis = getattr(upload, "analysis", None) or {}
    names = analysis.get("entry_preview") or []
    original_name = getattr(upload, "original_name", "")
    if original_name:
        names.append(original_name)
    return names


def _project_pdf_documents(project):
    return [
        {
            "id": document.id,
            "title": document.title,
            "file": document.file.url if document.file else "",
            "review_status": document.review_status,
        }
        for document in project.documents.filter(extension="pdf").order_by("-updated_at")[:20]
    ]


def _configuration_files(names):
    rows = []
    seen = set()
    for name in names:
        base = Path(str(name)).name.lower()
        if base not in CONFIG_FILE_NAMES and not base.endswith((".json", ".yaml", ".yml", ".toml", ".ini", ".conf")):
            continue
        if name in seen:
            continue
        seen.add(name)
        rows.append({"name": str(name), "kind": base})
    return rows
