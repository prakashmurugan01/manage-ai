import hashlib
import secrets
from datetime import timedelta

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import AgentCommand, DeploymentSignal, MachineAgent, ManagedProject, ProjectLogEntry, ProjectWebhookEvent, RuntimeMetric

SENSITIVE_KEYS = {"authorization", "cookie", "set-cookie", "x-api-key", "api_key", "token", "secret", "password", "access_token", "refresh_token"}


class AgentAuthenticationError(Exception):
    pass


def hash_agent_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_agent_token():
    token = f"mai_agent_{secrets.token_urlsafe(36)}"
    return token, token[:16], hash_agent_token(token)


def create_agent(owner, *, name, machine_id, environment, hostname="", os_name="", capabilities=None, metadata=None):
    token, prefix, token_hash = issue_agent_token()
    agent = MachineAgent.objects.create(
        owner=owner,
        name=name,
        machine_id=machine_id,
        environment=environment,
        hostname=hostname,
        os_name=os_name,
        token_prefix=prefix,
        token_hash=token_hash,
        capabilities=capabilities or {},
        metadata=metadata or {},
    )
    agent.plaintext_token = token
    return agent


def authenticate_agent_token(token):
    if not token:
        raise AgentAuthenticationError("Missing agent token.")
    token_hash = hash_agent_token(token)
    agent = MachineAgent.objects.filter(token_hash=token_hash, revoked_at__isnull=True).first()
    if not agent:
        raise AgentAuthenticationError("Invalid or revoked agent token.")
    return agent


def request_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    return (forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")) or "127.0.0.1"


def parse_time(value):
    if not value:
        return timezone.now()
    if hasattr(value, "tzinfo"):
        return value
    parsed = parse_datetime(str(value))
    if parsed:
        return parsed if timezone.is_aware(parsed) else timezone.make_aware(parsed)
    return timezone.now()


def redact(value):
    if isinstance(value, dict):
        safe = {}
        for key, nested in value.items():
            if str(key).lower() in SENSITIVE_KEYS:
                safe[key] = "[redacted]"
            else:
                safe[key] = redact(nested)
        return safe
    if isinstance(value, list):
        return [redact(item) for item in value[:200]]
    if isinstance(value, str) and len(value) > 12000:
        return f"{value[:12000]}...[truncated]"
    return value


def stable_project_id(agent, project):
    source = project.get("external_id") or project.get("id") or project.get("root_path") or project.get("name") or "project"
    raw = f"{agent.machine_id}:{source}:{project.get('environment') or agent.environment}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def root_path_hash(item):
    supplied = item.get("root_path_hash")
    if supplied:
        return str(supplied)
    root_path = item.get("root_path")
    if not root_path:
        return ""
    return hashlib.sha256(str(root_path).encode("utf-8")).hexdigest()


def score_health(project, latest_metric=None):
    score = 100
    if project.runtime_status in {ManagedProject.RuntimeStatus.ERROR, ManagedProject.RuntimeStatus.DEGRADED}:
        score -= 35
    if project.runtime_status == ManagedProject.RuntimeStatus.STOPPED:
        score -= 25
    if project.build_status == ManagedProject.BuildStatus.FAILING:
        score -= 25
    if project.deployment_status == ManagedProject.DeploymentStatus.FAILED:
        score -= 25
    if latest_metric:
        if latest_metric.cpu_percent >= 90:
            score -= 15
        if latest_metric.memory_percent >= 90:
            score -= 15
        if latest_metric.disk_percent >= 90:
            score -= 15
        if latest_metric.error_rate_percent >= 5:
            score -= 20
    return max(0, min(100, round(score)))


def analyze_webhook_event(event):
    findings = []
    recommendation = "No action required."
    severity = "healthy"
    if event.status in {ProjectWebhookEvent.Status.FAILED, ProjectWebhookEvent.Status.BLOCKED} or (event.response_code and event.response_code >= 400):
        severity = "critical"
        findings.append("Webhook delivery failed or returned an error response.")
        recommendation = "Inspect credentials, endpoint reachability, retry policy, and downstream service health."
    if event.processing_time_ms >= 2000:
        severity = "warning" if severity == "healthy" else severity
        findings.append("Processing latency exceeded the enterprise threshold.")
        recommendation = "Check queue depth, worker concurrency, and downstream API latency."
    if not event.signature_valid:
        severity = "critical"
        findings.append("Webhook signature validation failed.")
        recommendation = "Block source until signing secret and timestamp tolerance are verified."
    if event.threat_score >= 70:
        severity = "critical"
        findings.append("Payload matched high-risk security signals.")
        recommendation = "Quarantine event, rotate exposed credentials, and open a security incident."
    return {
        "severity": severity,
        "findings": findings or ["Event processed within expected bounds."],
        "recommendation": recommendation,
        "generated_at": timezone.now().isoformat(),
    }


def broadcast(kind, payload):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    async_to_sync(channel_layer.group_send)(
        "project_intelligence",
        {"type": "project.event", "event": {"kind": kind, "payload": payload, "ts": timezone.now().isoformat()}},
    )


@transaction.atomic
def ingest_agent_payload(agent, payload, *, ip_address=None):
    heartbeat = payload.get("heartbeat") or {}
    agent.name = heartbeat.get("name") or payload.get("agent_name") or agent.name
    agent.machine_id = heartbeat.get("machine_id") or payload.get("machine_id") or agent.machine_id
    agent.hostname = heartbeat.get("hostname") or agent.hostname
    agent.os_name = heartbeat.get("os_name") or agent.os_name
    agent.version = heartbeat.get("version") or payload.get("agent_version") or agent.version
    agent.environment = heartbeat.get("environment") or payload.get("environment") or agent.environment
    agent.capabilities = {**(agent.capabilities or {}), **(heartbeat.get("capabilities") or {})}
    agent.metadata = {**(agent.metadata or {}), **(heartbeat.get("metadata") or {})}
    agent.mark_seen(ip_address=ip_address)

    project_map = {}
    for item in payload.get("projects", []):
        external_id = item.get("external_id") or item.get("id") or stable_project_id(agent, item)
        environment = item.get("environment") or agent.environment
        project, _ = ManagedProject.objects.update_or_create(
            agent=agent,
            external_id=str(external_id),
            environment=environment,
            defaults={
                "name": item.get("name") or "Unnamed project",
                "developer_name": item.get("developer") or item.get("developer_name") or "",
                "machine_name": item.get("machine_name") or agent.hostname,
                "framework": item.get("framework") or "",
                "language": item.get("language") or "",
                "root_path_hash": root_path_hash(item),
                "repository_url": item.get("repository_url") or "",
                "runtime_status": item.get("runtime_status") or item.get("status") or ManagedProject.RuntimeStatus.UNKNOWN,
                "current_branch": item.get("current_branch") or item.get("branch") or "",
                "last_commit_sha": item.get("last_commit_sha") or "",
                "last_commit_message": item.get("last_commit_message") or "",
                "last_commit_author": item.get("last_commit_author") or "",
                "last_commit_at": parse_time(item.get("last_commit_at")) if item.get("last_commit_at") else None,
                "build_status": item.get("build_status") or ManagedProject.BuildStatus.UNKNOWN,
                "deployment_status": item.get("deployment_status") or ManagedProject.DeploymentStatus.NOT_DEPLOYED,
                "version": item.get("version") or "",
                "port": item.get("port") or None,
                "url": item.get("url") or "",
                "last_seen_at": timezone.now(),
                "metadata": redact(item.get("metadata") or {}),
            },
        )
        project_map[str(external_id)] = project

    metric_count = 0
    for item in payload.get("metrics", []):
        project = project_map.get(str(item.get("project_id") or item.get("external_id"))) or _find_project(agent, item)
        if not project:
            continue
        metric = RuntimeMetric.objects.create(
            agent=agent,
            project=project,
            cpu_percent=float(item.get("cpu_percent") or 0),
            memory_percent=float(item.get("memory_percent") or 0),
            memory_mb=float(item.get("memory_mb") or 0),
            disk_percent=float(item.get("disk_percent") or 0),
            network_rx_bps=int(item.get("network_rx_bps") or 0),
            network_tx_bps=int(item.get("network_tx_bps") or 0),
            active_users=int(item.get("active_users") or 0),
            requests_per_second=float(item.get("requests_per_second") or item.get("rps") or 0),
            error_rate_percent=float(item.get("error_rate_percent") or 0),
            latency_ms=int(item.get("latency_ms") or 0),
            process_count=int(item.get("process_count") or 0),
            container_count=int(item.get("container_count") or 0),
            recorded_at=parse_time(item.get("recorded_at")),
        )
        project.health_score = score_health(project, metric)
        project.save(update_fields=["health_score", "updated_at"])
        metric_count += 1

    log_count = 0
    for item in payload.get("logs", [])[:500]:
        project = project_map.get(str(item.get("project_id") or item.get("external_id"))) or _find_project(agent, item)
        if not project:
            continue
        ProjectLogEntry.objects.create(
            agent=agent,
            project=project,
            level=str(item.get("level") or ProjectLogEntry.Level.INFO).lower(),
            source=item.get("source") or "",
            message=str(item.get("message") or "")[:8000],
            trace_id=item.get("trace_id") or "",
            metadata=redact(item.get("metadata") or {}),
            timestamp=parse_time(item.get("timestamp")),
        )
        log_count += 1

    deployment_count = 0
    for item in payload.get("deployment_signals", [])[:200]:
        project = project_map.get(str(item.get("project_id") or item.get("external_id"))) or _find_project(agent, item)
        if not project:
            continue
        DeploymentSignal.objects.create(
            agent=agent,
            project=project,
            signal_type=item.get("signal_type") or DeploymentSignal.SignalType.READINESS,
            status=item.get("status") or DeploymentSignal.Status.PENDING,
            version=item.get("version") or "",
            release_id=item.get("release_id") or "",
            commit_sha=item.get("commit_sha") or "",
            risk_score=int(item.get("risk_score") or 0),
            summary=item.get("summary") or "",
            metadata=redact(item.get("metadata") or {}),
            created_at=parse_time(item.get("created_at")),
        )
        deployment_count += 1

    webhook_count = 0
    for item in payload.get("webhook_events", [])[:500]:
        project = project_map.get(str(item.get("project_id") or item.get("external_id"))) or _find_project(agent, item)
        event = ProjectWebhookEvent.objects.create(
            agent=agent,
            project=project,
            event_type=item.get("event_type") or "webhook.event",
            integration=item.get("integration") or "",
            direction=item.get("direction") or ProjectWebhookEvent.Direction.INCOMING,
            status=item.get("status") or ProjectWebhookEvent.Status.RECEIVED,
            processing_time_ms=int(item.get("processing_time_ms") or 0),
            response_code=item.get("response_code") or None,
            request_headers=redact(item.get("request_headers") or item.get("headers") or {}),
            request_body=redact(item.get("request_body") or item.get("payload") or {}),
            response_headers=redact(item.get("response_headers") or {}),
            response_body=redact(item.get("response_body") or {}),
            retry_history=redact(item.get("retry_history") or []),
            execution_trace=redact(item.get("execution_trace") or item.get("trace") or []),
            metadata=redact(item.get("metadata") or {}),
            signature_valid=bool(item.get("signature_valid", True)),
            threat_score=int(item.get("threat_score") or 0),
            occurred_at=parse_time(item.get("occurred_at")),
        )
        event.ai_analysis = analyze_webhook_event(event)
        event.save(update_fields=["ai_analysis"])
        webhook_count += 1

    result = {
        "agent_id": str(agent.id),
        "projects": len(project_map),
        "metrics": metric_count,
        "logs": log_count,
        "deployment_signals": deployment_count,
        "webhook_events": webhook_count,
    }
    broadcast("agent.ingested", result)
    return result


def _find_project(agent, item):
    external_id = item.get("project_id") or item.get("external_id")
    if external_id:
        project = ManagedProject.objects.filter(agent=agent, external_id=str(external_id)).first()
        if project:
            return project
    name = item.get("project_name") or item.get("name")
    if name:
        return ManagedProject.objects.filter(agent=agent, name=name).first()
    return None


def queued_commands_for(agent):
    commands = AgentCommand.objects.filter(
        agent=agent,
        status=AgentCommand.Status.QUEUED,
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
    now = timezone.now()
    rows = []
    for command in commands.order_by("created_at")[:50]:
        command.status = AgentCommand.Status.SENT
        command.sent_at = now
        command.save(update_fields=["status", "sent_at", "updated_at"])
        rows.append({
            "id": str(command.id),
            "command_type": command.command_type,
            "project_id": str(command.project_id) if command.project_id else "",
            "payload": command.payload,
            "created_at": command.created_at.isoformat(),
        })
    return rows


def mark_stale_agents(max_age_seconds=45):
    cutoff = timezone.now() - timedelta(seconds=max_age_seconds)
    stale = MachineAgent.objects.filter(status__in=[MachineAgent.Status.ONLINE, MachineAgent.Status.DEGRADED], last_seen_at__lt=cutoff)
    count = stale.update(status=MachineAgent.Status.OFFLINE, updated_at=timezone.now())
    if count:
        ManagedProject.objects.filter(agent__status=MachineAgent.Status.OFFLINE, runtime_status=ManagedProject.RuntimeStatus.RUNNING).update(
            runtime_status=ManagedProject.RuntimeStatus.UNKNOWN,
            updated_at=timezone.now(),
        )
        broadcast("agents.stale", {"count": count})
    return count
