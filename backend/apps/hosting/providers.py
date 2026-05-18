from datetime import timedelta
import time
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.utils import timezone

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
    HostingLink.Provider.CYBERIN: 4,
    HostingLink.Provider.HOSTINGRAJA: 4,
    HostingLink.Provider.BIGROCK: 4,
    HostingLink.Provider.HOSTING_HOME: 4,
    HostingLink.Provider.VERCEL: 4,
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
]


class ProviderError(Exception):
    pass


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


def sync_aws_instances():
    provider = HostingProvider.objects.get(provider=HostingProvider.Provider.AWS, name="AWS Production")
    if not getattr(settings, "AWS_ACCESS_KEY_ID", "") or not getattr(settings, "AWS_SECRET_ACCESS_KEY", ""):
        provider.last_error = "AWS credentials are not configured."
        provider.save(update_fields=["last_error", "updated_at"])
        return {"synced": 0, "error": provider.last_error}
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
    count = 0
    for reservation in ec2.describe_instances().get("Reservations", []):
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
                    "status": HostingLink.Status.ON if link.is_active else HostingLink.Status.OFF,
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
    if link.provider == HostingLink.Provider.AWS:
        _toggle_aws(link, enabled)
    elif link.provider == HostingLink.Provider.DIGITALOCEAN:
        _toggle_digitalocean(link, enabled)
    elif link.provider == HostingLink.Provider.NETLIFY:
        link.metadata = {**link.metadata, "simulated_off": not enabled}
    elif link.provider == HostingLink.Provider.VERCEL:
        vercel = VercelProject.objects.filter(hosted_project=link.project).first()
        if vercel:
            set_vercel_access(vercel, enabled, user=user)
    else:
        link.metadata = {
            **link.metadata,
            "simulated_off": not enabled,
            "control_mode": link.metadata.get("control_mode", "dns_redirect_or_maintenance"),
            "last_control_note": "Traditional hosting access simulated with DNS/redirect/maintenance mode.",
        }
    link.status = HostingLink.Status.ON if enabled else HostingLink.Status.OFF
    link.is_enabled = enabled
    link.health_status = HostingLink.Health.UNKNOWN if enabled else HostingLink.Health.DOWN
    link.save(update_fields=["status", "is_enabled", "health_status", "metadata", "updated_at"])
    HostingLifecycle.objects.create(
        project=link.project,
        event_type=HostingLifecycle.Event.PROVIDER_TOGGLED,
        performed_by=user if getattr(user, "is_authenticated", False) else None,
        notes=f"{link.provider} {link.label or link.external_id} toggled {'on' if enabled else 'off'}.",
    )
    return link


def monitor_link(link):
    started = time.monotonic()
    target = link.url or (f"https://{link.domain}" if link.domain else "")
    if not target:
        return link
    try:
        response = requests.get(target, timeout=8, allow_redirects=True)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        down = response.status_code >= 500
        link.last_http_status = response.status_code
    except requests.RequestException:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        down = True
        link.last_http_status = None
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


def _health_from_uptime(uptime):
    value = float(uptime or 0)
    if value >= 99:
        return HostingLink.Health.HEALTHY
    if value >= 95:
        return HostingLink.Health.DEGRADED
    return HostingLink.Health.DOWN


def _next_uptime(current, down):
    current = float(current or 100)
    sample = 0 if down else 100
    return round((current * 19 + sample) / 20, 2)


def previous_id(obj):
    return obj.id if obj else None
