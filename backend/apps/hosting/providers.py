from datetime import timedelta
from urllib.parse import urlparse

import requests
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .health import probe_url
from .models import HostedProject, HostingFailoverState, HostingLifecycle, HostingLink, HostingProvider, VercelProject
from .vercel import set_vercel_access


PROVIDER_PRIORITIES = {
    HostingLink.Provider.AWS: 1,
    HostingLink.Provider.AWS_S3: 1,
    HostingLink.Provider.AWS_CLOUDFRONT: 1,
    HostingLink.Provider.SITEGROUND: 2,
    HostingLink.Provider.SCALAHOSTING: 2,
    HostingLink.Provider.CLOUDWAYS: 2,
    HostingLink.Provider.HOSTINGER: 3,
    HostingLink.Provider.BLUEHOST: 3,
    HostingLink.Provider.GODADDY: 3,
    HostingLink.Provider.HOSTGATOR: 3,
    HostingLink.Provider.NETLIFY: 3,
    HostingLink.Provider.DIGITALOCEAN: 4,
    HostingLink.Provider.CLOUDFLARE: 2,
    HostingLink.Provider.CYBERIN: 4,
    HostingLink.Provider.HOSTINGRAJA: 4,
    HostingLink.Provider.BIGROCK: 4,
    HostingLink.Provider.HOSTING_HOME: 4,
    HostingLink.Provider.VERCEL: 4,
    HostingLink.Provider.RAILWAY: 4,
    HostingLink.Provider.RENDER: 4,
    HostingLink.Provider.FIREBASE: 4,
    HostingLink.Provider.SUPABASE: 4,
    HostingLink.Provider.GITHUB: 4,
    HostingLink.Provider.CPANEL: 3,
    HostingLink.Provider.WHM: 3,
    HostingLink.Provider.PLESK: 3,
}

API_CONTROLLED_PROVIDERS = {
    HostingLink.Provider.AWS,
    HostingLink.Provider.DIGITALOCEAN,
    HostingLink.Provider.HOSTINGER,
    HostingLink.Provider.VERCEL,
}

MANUAL_PROVIDER_DEFAULTS = [
    ("Cloudways Managed Cloud", HostingProvider.Provider.CLOUDWAYS, 2),
    ("Hostinger Web Hosting", HostingProvider.Provider.HOSTINGER, 3),
    ("ScalaHosting Managed VPS", HostingProvider.Provider.SCALAHOSTING, 2),
    ("SiteGround Google Cloud", HostingProvider.Provider.SITEGROUND, 2),
    ("Bluehost WordPress", HostingProvider.Provider.BLUEHOST, 3),
    ("GoDaddy Domains + VPS", HostingProvider.Provider.GODADDY, 3),
    ("HostGator Shared Hosting", HostingProvider.Provider.HOSTGATOR, 3),
    ("Cyberin India Hosting", HostingProvider.Provider.CYBERIN, 4),
    ("HostingRaja India Hosting", HostingProvider.Provider.HOSTINGRAJA, 4),
    ("BigRock India Hosting", HostingProvider.Provider.BIGROCK, 4),
    ("Hosting Home India", HostingProvider.Provider.HOSTING_HOME, 4),
    ("Cloudflare Edge Network", HostingProvider.Provider.CLOUDFLARE, 2),
    ("cPanel Shared Fleet", HostingProvider.Provider.CPANEL, 3),
    ("WHM Server Fleet", HostingProvider.Provider.WHM, 3),
    ("Plesk Server Fleet", HostingProvider.Provider.PLESK, 3),
    ("Railway Services", HostingProvider.Provider.RAILWAY, 4),
    ("Render Services", HostingProvider.Provider.RENDER, 4),
    ("Firebase Hosting", HostingProvider.Provider.FIREBASE, 4),
    ("Supabase Edge Stack", HostingProvider.Provider.SUPABASE, 4),
    ("GitHub Deployments", HostingProvider.Provider.GITHUB, 4),
]


class ProviderError(Exception):
    def __init__(self, message, details=None):
        super().__init__(message)
        self.details = details or []


def ensure_default_providers():
    defaults = [
        ("AWS Production", HostingProvider.Provider.AWS, 1),
        ("AWS S3 Static Hosting", HostingProvider.Provider.AWS_S3, 1),
        ("AWS CloudFront CDN", HostingProvider.Provider.AWS_CLOUDFRONT, 1),
        ("Netlify Backup", HostingProvider.Provider.NETLIFY, 3),
        ("DigitalOcean Backup", HostingProvider.Provider.DIGITALOCEAN, 4),
        ("Vercel Fallback", HostingProvider.Provider.VERCEL, 4),
    ] + MANUAL_PROVIDER_DEFAULTS
    providers = []
    for name, provider, priority in defaults:
        obj, _ = HostingProvider.objects.get_or_create(provider=provider, name=name, defaults={"priority": priority})
        if obj.priority != priority:
            obj.priority = priority
            obj.save(update_fields=["priority", "updated_at"])
        providers.append(obj)
    return providers


def sync_all_providers():
    ensure_default_providers()
    results = {
        "aws": sync_aws_instances(),
        "hostinger": sync_hostinger_virtual_machines(),
        "netlify": sync_netlify_sites(),
        "digitalocean": sync_digitalocean_droplets(),
        "vercel": sync_vercel_links(),
        "manual": sync_manual_provider_links(),
    }
    return results


def sync_manual_provider_links():
    ensure_default_providers()
    synced = 0
    for link in HostingLink.objects.select_related("provider_config").exclude(
        provider__in=[
            HostingLink.Provider.AWS,
            HostingLink.Provider.NETLIFY,
            HostingLink.Provider.DIGITALOCEAN,
            HostingLink.Provider.VERCEL,
        ]
    ):
        link.priority = PROVIDER_PRIORITIES.get(link.provider, link.priority)
        if link.provider_config:
            link.provider_config.last_synced_at = timezone.now()
            link.provider_config.last_error = ""
            link.provider_config.save(update_fields=["last_synced_at", "last_error", "updated_at"])
        if link.status == HostingLink.Status.UNKNOWN:
            link.status = HostingLink.Status.ON if link.is_enabled else HostingLink.Status.OFF
        link.metadata = {
            **link.metadata,
            "control_mode": link.metadata.get("control_mode", "dns_redirect_or_maintenance"),
            "sync_mode": "manual_or_provider_api",
        }
        link.save(update_fields=["priority", "status", "metadata", "updated_at"])
        synced += 1
    return {"synced": synced, "mode": "manual providers normalized"}


def sync_hostinger_virtual_machines():
    provider = HostingProvider.objects.get(provider=HostingProvider.Provider.HOSTINGER, name="Hostinger Web Hosting")
    token = getattr(settings, "HOSTINGER_API_TOKEN", "")
    if not token:
        provider.last_error = "HOSTINGER_API_TOKEN is not configured."
        provider.save(update_fields=["last_error", "updated_at"])
        return {"synced": 0, "error": provider.last_error}
    try:
        payload = _request_json(
            "GET",
            "https://developers.hostinger.com/api/vps/v1/virtual-machines",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
    except ProviderError as exc:
        provider.last_error = f"Hostinger API error: {exc}"
        provider.save(update_fields=["last_error", "updated_at"])
        return {"synced": 0, "error": provider.last_error}

    machines = payload if isinstance(payload, list) else payload.get("data") or payload.get("virtual_machines") or []
    count = 0
    for machine in machines:
        vm_id = str(machine.get("id") or machine.get("virtual_machine_id") or machine.get("uuid") or "")
        if not vm_id:
            continue
        name = machine.get("name") or machine.get("hostname") or f"Hostinger VPS {vm_id}"
        ip = _hostinger_public_ip(machine)
        fallback = ip or machine.get("hostname") or vm_id
        project = _project_for_provider(name, HostingLink.Provider.HOSTINGER, fallback)
        status = str(machine.get("state") or machine.get("status") or "").lower()
        is_running = status in {"running", "started", "active", "online"}
        HostingLink.objects.update_or_create(
            project=project,
            provider=HostingLink.Provider.HOSTINGER,
            external_id=vm_id,
            defaults={
                "provider_config": provider,
                "priority": PROVIDER_PRIORITIES[HostingLink.Provider.HOSTINGER],
                "server_type": HostingLink.ServerType.VPS,
                "tag": HostingLink.LinkTag.PRODUCTION,
                "label": name,
                "url": _absolute_url(ip or ""),
                "domain": machine.get("hostname", "") or "",
                "region": str(machine.get("data_center") or machine.get("datacenter") or machine.get("location") or ""),
                "ip_address": ip,
                "status": HostingLink.Status.ON if is_running else HostingLink.Status.OFF if status in {"stopped", "offline"} else HostingLink.Status.UNKNOWN,
                "health_status": HostingLink.Health.HEALTHY if is_running else HostingLink.Health.DOWN if status in {"stopped", "offline"} else HostingLink.Health.UNKNOWN,
                "metadata": machine,
            },
        )
        count += 1
    provider.last_synced_at = timezone.now()
    provider.last_error = ""
    provider.config = {**provider.config, "last_warning": ""}
    provider.save(update_fields=["last_synced_at", "last_error", "config", "updated_at"])
    return {"synced": count}


def sync_aws_instances():
    provider = HostingProvider.objects.get(provider=HostingProvider.Provider.AWS, name="AWS Production")
    if not getattr(settings, "AWS_ACCESS_KEY_ID", "") or not getattr(settings, "AWS_SECRET_ACCESS_KEY", ""):
        provider.last_error = "AWS credentials are not configured."
        provider.save(update_fields=["last_error", "updated_at"])
        return {"synced": 0, "error": provider.last_error}
    if provider.last_error == "AWS credentials are not configured.":
        provider.last_error = ""
        provider.save(update_fields=["last_error", "updated_at"])
    try:
        import boto3
    except ImportError as exc:
        provider.last_error = "boto3 is not installed."
        provider.save(update_fields=["last_error", "updated_at"])
        return {"synced": 0, "error": str(exc)}

    region = getattr(settings, "AWS_REGION", "us-east-1")
    ec2 = boto3.client(
        "ec2",
        region_name=region,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )
    try:
        reservations = ec2.describe_instances().get("Reservations", [])
    except Exception as exc:
        error = getattr(exc, "response", {}).get("Error", {})
        code = error.get("Code", "")
        if code in {"UnauthorizedOperation", "AccessDenied", "AccessDeniedException"}:
            provider.last_error = ""
            provider.last_synced_at = timezone.now()
            provider.config = {
                **provider.config,
                "last_warning": "AWS connected with limited permissions. Grant ec2:DescribeInstances to sync EC2 servers.",
                "last_warning_code": code,
            }
            provider.save(update_fields=["last_error", "last_synced_at", "config", "updated_at"])
            return {"synced": 0, "warning": provider.config["last_warning"], "code": code}
        provider.last_error = f"AWS API error: {exc}"
        provider.save(update_fields=["last_error", "updated_at"])
        return {"synced": 0, "error": provider.last_error}

    count = 0
    for reservation in reservations:
        for instance in reservation.get("Instances", []):
            name = _tag_value(instance.get("Tags", []), "Name") or instance["InstanceId"]
            public_dns = instance.get("PublicDnsName", "")
            public_ip = instance.get("PublicIpAddress")
            project = _project_for_provider(name, HostingLink.Provider.AWS, public_dns or public_ip or instance["InstanceId"])
            HostingLink.objects.update_or_create(
                project=project,
                provider=HostingLink.Provider.AWS,
                external_id=instance["InstanceId"],
                defaults={
                    "provider_config": provider,
                    "priority": PROVIDER_PRIORITIES[HostingLink.Provider.AWS],
                    "server_type": HostingLink.ServerType.CLOUD,
                    "tag": HostingLink.LinkTag.PRODUCTION,
                    "label": name,
                    "url": _absolute_url(public_dns or public_ip or ""),
                    "domain": public_dns or "",
                    "region": region,
                    "ip_address": public_ip,
                    "status": HostingLink.Status.ON if instance.get("State", {}).get("Name") == "running" else HostingLink.Status.OFF,
                    "health_status": HostingLink.Health.HEALTHY if instance.get("State", {}).get("Name") == "running" else HostingLink.Health.DOWN,
                    "metadata": {"instance_type": instance.get("InstanceType"), "state": instance.get("State", {})},
                },
            )
            count += 1
    provider.last_synced_at = timezone.now()
    provider.last_error = ""
    provider.save(update_fields=["last_synced_at", "last_error", "updated_at"])
    return {"synced": count}


def sync_netlify_sites():
    provider = HostingProvider.objects.get(provider=HostingProvider.Provider.NETLIFY, name="Netlify Backup")
    token = getattr(settings, "NETLIFY_API_TOKEN", "")
    if not token:
        provider.last_error = "NETLIFY_API_TOKEN is not configured."
        provider.save(update_fields=["last_error", "updated_at"])
        return {"synced": 0, "error": provider.last_error}
    payload = _request_json("GET", "https://api.netlify.com/api/v1/sites", headers={"Authorization": f"Bearer {token}"})
    count = 0
    for site in payload:
        name = site.get("name") or site.get("id")
        url = site.get("ssl_url") or site.get("url") or site.get("default_domain", "")
        project = _project_for_provider(name, HostingLink.Provider.NETLIFY, url)
        HostingLink.objects.update_or_create(
            project=project,
            provider=HostingLink.Provider.NETLIFY,
            external_id=site.get("id", ""),
            defaults={
                "provider_config": provider,
                    "priority": PROVIDER_PRIORITIES[HostingLink.Provider.NETLIFY],
                    "server_type": HostingLink.ServerType.STATIC,
                    "tag": HostingLink.LinkTag.BACKUP,
                "label": name,
                "url": _absolute_url(url),
                "domain": urlparse(_absolute_url(url)).netloc,
                "status": HostingLink.Status.ON if not site.get("force_ssl") is None else HostingLink.Status.UNKNOWN,
                "health_status": HostingLink.Health.UNKNOWN,
                "metadata": {"published_deploy": site.get("published_deploy"), "admin_url": site.get("admin_url")},
            },
        )
        count += 1
    provider.last_synced_at = timezone.now()
    provider.last_error = ""
    provider.save(update_fields=["last_synced_at", "last_error", "updated_at"])
    return {"synced": count}


def sync_digitalocean_droplets():
    provider = HostingProvider.objects.get(provider=HostingProvider.Provider.DIGITALOCEAN, name="DigitalOcean Backup")
    token = getattr(settings, "DIGITALOCEAN_API_TOKEN", "")
    if not token:
        provider.last_error = "DIGITALOCEAN_API_TOKEN is not configured."
        provider.save(update_fields=["last_error", "updated_at"])
        return {"synced": 0, "error": provider.last_error}
    payload = _request_json("GET", "https://api.digitalocean.com/v2/droplets", headers={"Authorization": f"Bearer {token}"})
    count = 0
    for droplet in payload.get("droplets", []):
        ip = _public_ipv4(droplet)
        project = _project_for_provider(droplet.get("name") or str(droplet.get("id")), HostingLink.Provider.DIGITALOCEAN, ip or str(droplet.get("id")))
        status = droplet.get("status")
        HostingLink.objects.update_or_create(
            project=project,
            provider=HostingLink.Provider.DIGITALOCEAN,
            external_id=str(droplet.get("id")),
            defaults={
                "provider_config": provider,
                "priority": PROVIDER_PRIORITIES[HostingLink.Provider.DIGITALOCEAN],
                "server_type": HostingLink.ServerType.CLOUD,
                "tag": HostingLink.LinkTag.BACKUP,
                "label": droplet.get("name", ""),
                "url": _absolute_url(ip or ""),
                "domain": "",
                "region": droplet.get("region", {}).get("slug", ""),
                "ip_address": ip,
                "status": HostingLink.Status.ON if status == "active" else HostingLink.Status.OFF,
                "health_status": HostingLink.Health.HEALTHY if status == "active" else HostingLink.Health.DOWN,
                "metadata": {"status": status, "size": droplet.get("size_slug")},
            },
        )
        count += 1
    provider.last_synced_at = timezone.now()
    provider.last_error = ""
    provider.save(update_fields=["last_synced_at", "last_error", "updated_at"])
    return {"synced": count}


def sync_vercel_links():
    provider = HostingProvider.objects.get(provider=HostingProvider.Provider.VERCEL, name="Vercel Fallback")
    count = 0
    for vercel_project in VercelProject.objects.select_related("hosted_project").prefetch_related("links"):
        if not vercel_project.hosted_project:
            continue
        for link in vercel_project.links.all():
            deployment_state = str(vercel_project.latest_deployment_status or "").upper()
            HostingLink.objects.update_or_create(
                project=vercel_project.hosted_project,
                provider=HostingLink.Provider.VERCEL,
                external_id=str(link.id),
                defaults={
                    "provider_config": provider,
                    "priority": PROVIDER_PRIORITIES[HostingLink.Provider.VERCEL],
                    "server_type": HostingLink.ServerType.CLOUD,
                    "tag": HostingLink.LinkTag.BACKUP,
                    "label": link.tag,
                    "url": link.url,
                    "domain": link.domain,
                    "status": _vercel_link_status(link.is_active, deployment_state),
                    "health_status": _health_from_uptime(link.uptime_percentage),
                    "response_time_ms": link.response_time_ms,
                    "uptime_percentage": link.uptime_percentage,
                    "last_http_status": link.last_http_status,
                    "last_checked_at": link.last_checked_at,
                    "metadata": {"vercel_project": vercel_project.vercel_id},
                },
            )
            count += 1
    provider.last_synced_at = timezone.now()
    provider.last_error = ""
    provider.save(update_fields=["last_synced_at", "last_error", "updated_at"])
    return {"synced": count}


def toggle_hosting_link(link, enabled, user=None):
    control_result = _apply_provider_access(link, enabled, user=user)
    link.status = HostingLink.Status.ON if enabled else HostingLink.Status.OFF
    link.is_enabled = enabled
    link.is_active = bool(enabled and link.priority == 1)
    link.health_status = HostingLink.Health.UNKNOWN if enabled else HostingLink.Health.DOWN
    link.metadata = {
        **(link.metadata or {}),
        "access_state": "enabled" if enabled else "disabled",
        "access_control": control_result["mode"],
        "provider_access_blocked": control_result["blocked"],
        "last_access_action_at": timezone.now().isoformat(),
        "last_access_action_by": getattr(user, "id", None) if getattr(user, "is_authenticated", False) else None,
        "last_access_message": control_result["message"],
    }
    if not enabled:
        link.metadata["disabled_url"] = link.url or link.domain
    link.save(update_fields=["status", "is_enabled", "is_active", "health_status", "metadata", "updated_at"])
    HostingLifecycle.objects.create(
        project=link.project,
        event_type=HostingLifecycle.Event.PROVIDER_TOGGLED,
        performed_by=user if getattr(user, "is_authenticated", False) else None,
        notes=f"{link.provider} {link.label or link.external_id} toggled {'on' if enabled else 'off'}.",
    )
    return link


def _apply_provider_access(link, enabled, user=None):
    if link.provider == HostingLink.Provider.AWS:
        _toggle_aws(link, enabled)
        return {"mode": "provider_api", "blocked": not enabled, "message": "AWS instance power state changed."}
    if link.provider == HostingLink.Provider.DIGITALOCEAN:
        _toggle_digitalocean(link, enabled)
        return {"mode": "provider_api", "blocked": not enabled, "message": "DigitalOcean droplet power state changed."}
    if link.provider == HostingLink.Provider.HOSTINGER:
        _toggle_hostinger(link, enabled)
        return {"mode": "provider_api", "blocked": not enabled, "message": "Hostinger VPS power state changed."}
    if link.provider == HostingLink.Provider.VERCEL:
        vercel = VercelProject.objects.filter(hosted_project=link.project).first()
        if vercel:
            _status_obj, errors = set_vercel_access(vercel, enabled, user=user)
            if errors:
                return {"mode": "provider_api_partial", "blocked": not enabled, "message": f"Vercel access updated with {len(errors)} domain warning(s)."}
            return {"mode": "provider_api", "blocked": not enabled, "message": "Vercel domains updated."}
    return {
        "mode": "logical_provider_state",
        "blocked": False,
        "message": (
            f"{link.get_provider_display()} does not expose a safe public pause API in this integration. "
            "ManageAI disabled the project state, hides operational access, stops monitoring, and records the provider action for follow-up."
        ),
    }


def toggle_hosted_project_access(project, enabled, user=None, reason="", source="hosting.manager"):
    actor = user if getattr(user, "is_authenticated", False) else None
    enabled = bool(enabled)
    links = list(project.hosting_links.select_related("provider_config").order_by("priority", "provider", "id"))
    original_project = {
        "link_is_active": project.link_is_active,
        "status": project.status,
        "tag": project.tag,
        "archived_at": project.archived_at,
    }
    original_links = {
        link.id: {
            "status": link.status,
            "is_enabled": link.is_enabled,
            "is_active": link.is_active,
            "health_status": link.health_status,
            "metadata": dict(link.metadata or {}),
        }
        for link in links
    }
    changed_links = []

    try:
        for link in links:
            toggle_hosting_link(link, enabled, user=actor)
            changed_links.append(link)
    except ProviderError as exc:
        rollback_errors = _rollback_project_toggle(project, original_project, original_links, changed_links, actor)
        details = [{"detail": str(exc), "provider_errors": getattr(exc, "details", [])}, *rollback_errors]
        raise ProviderError("Hosting access was not changed because at least one provider rejected the toggle.", details=details) from exc

    with transaction.atomic():
        project.refresh_from_db()
        project.link_is_active = enabled
        project.status = HostedProject.Status.LIVE if enabled else HostedProject.Status.DISABLED
        project.tag = "active" if enabled else "disabled"
        project.server_status = HostedProject.ServerStatus.UNKNOWN if enabled else HostedProject.ServerStatus.OFFLINE
        project.last_checked_at = timezone.now()
        update_fields = ["link_is_active", "status", "tag", "server_status", "last_checked_at"]
        if enabled and project.archived_at:
            project.archived_at = None
            update_fields.append("archived_at")
        project.save(update_fields=update_fields)
        HostingLifecycle.objects.create(
            project=project,
            event_type=HostingLifecycle.Event.LINK_ENABLED if enabled else HostingLifecycle.Event.LINK_DISABLED,
            performed_by=actor,
            notes=reason or f"{source} set hosting {'active' if enabled else 'disabled'}.",
        )

    management_project = None
    try:
        from apps.projects.services import sync_project_from_hosting

        management_project = sync_project_from_hosting(project, actor=actor)
    except Exception:
        management_project = None
    _notify_hosting_access_changed(project, enabled, actor, management_project)
    _broadcast_hosting_project(project, event="hosting.project.enabled" if enabled else "hosting.project.disabled")
    return project


def _rollback_project_toggle(project, original_project, original_links, changed_links, actor):
    errors = []
    for link in reversed(changed_links):
        snapshot = original_links.get(link.id)
        if not snapshot:
            continue
        try:
            toggle_hosting_link(link, snapshot["is_enabled"], user=actor)
            link.refresh_from_db()
            link.status = snapshot["status"]
            link.is_active = snapshot["is_active"]
            link.health_status = snapshot["health_status"]
            link.metadata = snapshot["metadata"]
            link.save(update_fields=["status", "is_active", "health_status", "metadata", "updated_at"])
        except Exception as exc:
            errors.append({"link": link.id, "provider": link.provider, "rollback_error": str(exc)})
    HostedProject.objects.filter(id=project.id).update(**original_project)
    project.refresh_from_db()
    return errors


def _notify_hosting_access_changed(project, enabled, actor, management_project=None):
    try:
        from apps.notifications.services import notify_user
    except Exception:
        return

    User = get_user_model()
    role_values = []
    if hasattr(User, "Role"):
        role_values = [getattr(User.Role, "SUPER_ADMIN", None), getattr(User.Role, "ADMIN", None)]
    recipients = set(
        User.objects.filter(
            Q(is_superuser=True)
            | Q(is_staff=True)
            | Q(role__in=[role for role in role_values if role])
        ).values_list("id", flat=True)
    )
    if management_project:
        recipients.update(
            item
            for item in [
                management_project.owner_id,
                management_project.created_by_id,
                management_project.client_id,
                *management_project.admins.values_list("id", flat=True),
                *management_project.developers.values_list("id", flat=True),
            ]
            if item
        )
    if actor:
        recipients.add(actor.id)

    title = f"Hosting {'enabled' if enabled else 'disabled'}"
    message = f"{project.name} ({project.domain}) is now {'Active' if enabled else 'Disabled'}."
    notification_type = "SUCCESS" if enabled else "ALERT"
    urgency = "info" if enabled else "warning"
    for recipient in User.objects.filter(id__in=recipients):
        try:
            notify_user(
                recipient=recipient,
                sender=actor,
                title=title,
                message=message,
                type=notification_type,
                urgency=urgency,
                project=management_project,
                hosted_project=project,
            )
        except Exception:
            pass


def _broadcast_hosting_project(project, event="hosting.project.updated"):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    payload = {
        "id": project.id,
        "name": project.name,
        "domain": project.domain,
        "deploy_url": project.deploy_url,
        "hosting_platform": project.hosting_platform,
        "status": project.status,
        "tag": project.tag,
        "server_status": project.server_status,
        "link_is_active": project.link_is_active,
        "response_time_ms": project.response_time_ms,
        "uptime_percentage": float(project.uptime_percentage or 0),
        "last_checked_at": project.last_checked_at.isoformat() if project.last_checked_at else None,
    }
    recipients = set()
    User = get_user_model()
    role_values = []
    if hasattr(User, "Role"):
        role_values = [getattr(User.Role, "SUPER_ADMIN", None), getattr(User.Role, "ADMIN", None)]
    recipients.update(
        User.objects.filter(
            Q(is_superuser=True)
            | Q(is_staff=True)
            | Q(role__in=[role for role in role_values if role])
        ).values_list("id", flat=True)
    )
    for user_id in recipients:
        async_to_sync(channel_layer.group_send)(
            f"user_{user_id}",
            {"type": "hosting.event", "event": event, "project": payload},
        )


def monitor_link(link):
    target = link.url or (f"https://{link.domain}" if link.domain else "")
    if not target:
        return link
    result = probe_url(target, timeout=8, retries=2)
    elapsed_ms = result.response_time_ms
    down = not result.online
    link.last_http_status = result.status_code
    link.response_time_ms = elapsed_ms
    link.health_status = HostingLink.Health.DOWN if down else HostingLink.Health.DEGRADED if elapsed_ms > 2500 else HostingLink.Health.HEALTHY
    link.status = HostingLink.Status.OFF if down and link.status == HostingLink.Status.UNKNOWN else link.status
    link.uptime_percentage = _next_uptime(link.uptime_percentage, down)
    link.last_checked_at = timezone.now()
    link.save(update_fields=["response_time_ms", "health_status", "status", "uptime_percentage", "last_http_status", "last_checked_at", "updated_at"])
    return link


def evaluate_failover(project):
    state, _ = HostingFailoverState.objects.get_or_create(project=project)
    links = list(project.hosting_links.filter(is_enabled=True).order_by("priority", "provider", "id"))
    best = next((link for link in links if link.health_status in {HostingLink.Health.HEALTHY, HostingLink.Health.UNKNOWN} and link.status != HostingLink.Status.OFF), None)
    if not best and links:
        best = links[-1]
    previous = state.active_link
    for link in links:
        link.is_active = bool(best and link.id == best.id)
        if link.is_active:
            link.last_failover_at = timezone.now()
        link.save(update_fields=["is_active", "last_failover_at", "updated_at"])
    state.active_link = best
    state.last_reason = "Selected highest-priority healthy provider." if best else "No enabled hosting links are available."
    state.last_evaluated_at = timezone.now()
    state.save(update_fields=["active_link", "last_reason", "last_evaluated_at", "updated_at"])
    if best and previous_id(previous) != best.id:
        project.deploy_url = best.url or project.deploy_url
        project.hosting_platform = best.provider
        project.link_is_active = True
        project.server_status = HostedProject.ServerStatus.ONLINE if best.health_status == HostingLink.Health.HEALTHY else HostedProject.ServerStatus.UNKNOWN
        project.save(update_fields=["deploy_url", "hosting_platform", "link_is_active", "server_status"])
        HostingLifecycle.objects.create(project=project, event_type=HostingLifecycle.Event.FAILOVER, notes=f"Active hosting switched to {best.provider} priority {best.priority}.")
    return state


def failover_all_projects():
    states = []
    for project in HostedProject.objects.prefetch_related("hosting_links"):
        for link in project.hosting_links.filter(is_enabled=True):
            monitor_link(link)
        states.append(evaluate_failover(project))
    return states


def _toggle_aws(link, enabled):
    try:
        import boto3
    except ImportError as exc:
        raise ProviderError("boto3 is not installed.") from exc
    ec2 = boto3.client(
        "ec2",
        region_name=link.region or getattr(settings, "AWS_REGION", "us-east-1"),
        aws_access_key_id=getattr(settings, "AWS_ACCESS_KEY_ID", ""),
        aws_secret_access_key=getattr(settings, "AWS_SECRET_ACCESS_KEY", ""),
    )
    if enabled:
        ec2.start_instances(InstanceIds=[link.external_id])
    else:
        ec2.stop_instances(InstanceIds=[link.external_id])


def _toggle_digitalocean(link, enabled):
    token = getattr(settings, "DIGITALOCEAN_API_TOKEN", "")
    if not token:
        raise ProviderError("DIGITALOCEAN_API_TOKEN is not configured.")
    action = "power_on" if enabled else "power_off"
    _request_json("POST", f"https://api.digitalocean.com/v2/droplets/{link.external_id}/actions", headers={"Authorization": f"Bearer {token}"}, json={"type": action})


def _toggle_hostinger(link, enabled):
    token = getattr(settings, "HOSTINGER_API_TOKEN", "")
    if not token:
        raise ProviderError("HOSTINGER_API_TOKEN is not configured.")
    if not link.external_id:
        raise ProviderError("Hostinger VPS external_id is required.")
    action = "start" if enabled else "stop"
    _request_json(
        "POST",
        f"https://developers.hostinger.com/api/vps/v1/virtual-machines/{link.external_id}/{action}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )


def _request_json(method, url, headers=None, json=None):
    response = requests.request(method, url, headers=headers or {}, json=json, timeout=20)
    if response.status_code >= 400:
        raise ProviderError(response.text)
    return response.json() if response.content else {}


def _project_for_provider(name, provider, fallback):
    domain = urlparse(_absolute_url(fallback)).netloc or f"{provider}-{name}".lower().replace(" ", "-")
    project, _ = HostedProject.objects.get_or_create(
        domain=domain,
        defaults={
            "name": name,
            "client_name": provider.upper(),
            "hosting_platform": provider,
            "deploy_url": _absolute_url(fallback),
            "status": HostedProject.Status.LIVE,
            "tag": "active",
            "expiry_date": timezone.localdate() + timedelta(days=365),
        },
    )
    return project


def _absolute_url(value):
    if not value:
        return ""
    return value if str(value).startswith(("http://", "https://")) else f"https://{value}"


def _tag_value(tags, key):
    for tag in tags:
        if tag.get("Key") == key:
            return tag.get("Value")
    return ""


def _public_ipv4(droplet):
    for net in droplet.get("networks", {}).get("v4", []):
        if net.get("type") == "public":
            return net.get("ip_address")
    return None


def _hostinger_public_ip(machine):
    candidates = [
        machine.get("ipv4"),
        machine.get("ip"),
        machine.get("ip_address"),
        machine.get("public_ip"),
    ]
    for value in candidates:
        if isinstance(value, str) and value:
            return value
    for key in ("ips", "ip_addresses", "addresses"):
        values = machine.get(key)
        if isinstance(values, list):
            for item in values:
                if isinstance(item, str) and item:
                    return item
                if isinstance(item, dict):
                    value = item.get("ip") or item.get("address") or item.get("ip_address")
                    if value:
                        return value
    return None


def _health_from_uptime(uptime):
    value = float(uptime or 0)
    if value >= 99:
        return HostingLink.Health.HEALTHY
    if value >= 95:
        return HostingLink.Health.DEGRADED
    return HostingLink.Health.DOWN


def _vercel_link_status(is_active, deployment_state):
    if deployment_state in {"BUILDING", "QUEUED", "INITIALIZING"}:
        return HostingLink.Status.BUILDING
    if deployment_state in {"ERROR", "CANCELED"}:
        return HostingLink.Status.ERROR
    return HostingLink.Status.ON if is_active else HostingLink.Status.OFF


def _next_uptime(current, down):
    current = float(current or 100)
    sample = 0 if down else 100
    return round((current * 19 + sample) / 20, 2)


def previous_id(obj):
    return obj.id if obj else None
