import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class MachineAgent(models.Model):
    class Status(models.TextChoices):
        ONLINE = "online", "Online"
        DEGRADED = "degraded", "Degraded"
        OFFLINE = "offline", "Offline"
        REVOKED = "revoked", "Revoked"

    class Environment(models.TextChoices):
        LOCALHOST = "localhost", "Localhost"
        DEVELOPMENT = "development", "Development"
        QA = "qa", "QA"
        STAGING = "staging", "Staging"
        PRODUCTION = "production", "Production"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="project_agents", on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=180)
    machine_id = models.CharField(max_length=160, db_index=True)
    hostname = models.CharField(max_length=255, blank=True)
    os_name = models.CharField(max_length=120, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    environment = models.CharField(max_length=24, choices=Environment.choices, default=Environment.DEVELOPMENT, db_index=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.OFFLINE, db_index=True)
    version = models.CharField(max_length=40, blank=True)
    token_prefix = models.CharField(max_length=16, unique=True, db_index=True)
    token_hash = models.CharField(max_length=128, unique=True)
    capabilities = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True, db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["environment", "status"]),
            models.Index(fields=["machine_id", "environment"]),
        ]

    def mark_seen(self, ip_address=None):
        self.status = self.Status.ONLINE
        self.last_seen_at = timezone.now()
        if ip_address:
            self.ip_address = ip_address
        self.save(update_fields=["status", "last_seen_at", "ip_address", "updated_at"])

    def __str__(self):
        return f"{self.name} ({self.machine_id})"


class ManagedProject(models.Model):
    class RuntimeStatus(models.TextChoices):
        RUNNING = "running", "Running"
        STOPPED = "stopped", "Stopped"
        DEGRADED = "degraded", "Degraded"
        ERROR = "error", "Error"
        UNKNOWN = "unknown", "Unknown"

    class BuildStatus(models.TextChoices):
        PASSING = "passing", "Passing"
        FAILING = "failing", "Failing"
        BUILDING = "building", "Building"
        UNKNOWN = "unknown", "Unknown"

    class DeploymentStatus(models.TextChoices):
        NOT_DEPLOYED = "not_deployed", "Not deployed"
        READY = "ready", "Ready"
        DEPLOYED = "deployed", "Deployed"
        FAILED = "failed", "Failed"
        ROLLBACK_READY = "rollback_ready", "Rollback ready"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent = models.ForeignKey(MachineAgent, related_name="projects", on_delete=models.SET_NULL, null=True, blank=True)
    linked_project = models.ForeignKey("projects.Project", related_name="intelligence_nodes", on_delete=models.SET_NULL, null=True, blank=True)
    external_id = models.CharField(max_length=180, db_index=True)
    name = models.CharField(max_length=220)
    developer_name = models.CharField(max_length=180, blank=True)
    machine_name = models.CharField(max_length=255, blank=True)
    environment = models.CharField(max_length=24, choices=MachineAgent.Environment.choices, default=MachineAgent.Environment.DEVELOPMENT, db_index=True)
    framework = models.CharField(max_length=80, blank=True, db_index=True)
    language = models.CharField(max_length=80, blank=True)
    root_path_hash = models.CharField(max_length=128, blank=True, db_index=True)
    repository_url = models.URLField(blank=True)
    runtime_status = models.CharField(max_length=24, choices=RuntimeStatus.choices, default=RuntimeStatus.UNKNOWN, db_index=True)
    current_branch = models.CharField(max_length=160, blank=True)
    last_commit_sha = models.CharField(max_length=80, blank=True)
    last_commit_message = models.CharField(max_length=500, blank=True)
    last_commit_author = models.CharField(max_length=180, blank=True)
    last_commit_at = models.DateTimeField(null=True, blank=True)
    build_status = models.CharField(max_length=24, choices=BuildStatus.choices, default=BuildStatus.UNKNOWN, db_index=True)
    deployment_status = models.CharField(max_length=32, choices=DeploymentStatus.choices, default=DeploymentStatus.NOT_DEPLOYED, db_index=True)
    version = models.CharField(max_length=80, blank=True)
    port = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    url = models.URLField(blank=True)
    health_score = models.PositiveSmallIntegerField(default=0)
    last_seen_at = models.DateTimeField(null=True, blank=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["environment", "name"]
        constraints = [
            models.UniqueConstraint(fields=["agent", "external_id", "environment"], name="unique_agent_project_environment")
        ]
        indexes = [
            models.Index(fields=["environment", "runtime_status"]),
            models.Index(fields=["framework", "build_status"]),
            models.Index(fields=["deployment_status", "updated_at"]),
        ]

    def __str__(self):
        return f"{self.name} [{self.environment}]"


class RuntimeMetric(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(ManagedProject, related_name="metrics", on_delete=models.CASCADE)
    agent = models.ForeignKey(MachineAgent, related_name="metrics", on_delete=models.SET_NULL, null=True, blank=True)
    cpu_percent = models.FloatField(default=0)
    memory_percent = models.FloatField(default=0)
    memory_mb = models.FloatField(default=0)
    disk_percent = models.FloatField(default=0)
    network_rx_bps = models.BigIntegerField(default=0)
    network_tx_bps = models.BigIntegerField(default=0)
    active_users = models.PositiveIntegerField(default=0)
    requests_per_second = models.FloatField(default=0)
    error_rate_percent = models.FloatField(default=0)
    latency_ms = models.PositiveIntegerField(default=0)
    process_count = models.PositiveIntegerField(default=0)
    container_count = models.PositiveIntegerField(default=0)
    recorded_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-recorded_at"]
        indexes = [models.Index(fields=["project", "-recorded_at"]), models.Index(fields=["agent", "-recorded_at"])]


class ProjectLogEntry(models.Model):
    class Level(models.TextChoices):
        DEBUG = "debug", "Debug"
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        ERROR = "error", "Error"
        CRITICAL = "critical", "Critical"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(ManagedProject, related_name="logs", on_delete=models.CASCADE)
    agent = models.ForeignKey(MachineAgent, related_name="logs", on_delete=models.SET_NULL, null=True, blank=True)
    level = models.CharField(max_length=16, choices=Level.choices, default=Level.INFO, db_index=True)
    source = models.CharField(max_length=120, blank=True, db_index=True)
    message = models.TextField()
    trace_id = models.CharField(max_length=120, blank=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [models.Index(fields=["project", "level", "-timestamp"])]


class DeploymentSignal(models.Model):
    class SignalType(models.TextChoices):
        BUILD = "build", "Build"
        DEPLOYMENT = "deployment", "Deployment"
        ROLLBACK = "rollback", "Rollback"
        READINESS = "readiness", "Readiness"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        RISKY = "risky", "Risky"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(ManagedProject, related_name="deployment_signals", on_delete=models.CASCADE)
    agent = models.ForeignKey(MachineAgent, related_name="deployment_signals", on_delete=models.SET_NULL, null=True, blank=True)
    signal_type = models.CharField(max_length=24, choices=SignalType.choices, db_index=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDING, db_index=True)
    version = models.CharField(max_length=80, blank=True)
    release_id = models.CharField(max_length=160, blank=True, db_index=True)
    commit_sha = models.CharField(max_length=80, blank=True)
    risk_score = models.PositiveSmallIntegerField(default=0)
    summary = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]


class ProjectWebhookEvent(models.Model):
    class Direction(models.TextChoices):
        INCOMING = "incoming", "Incoming"
        OUTGOING = "outgoing", "Outgoing"

    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        PROCESSED = "processed", "Processed"
        FAILED = "failed", "Failed"
        RETRIED = "retried", "Retried"
        BLOCKED = "blocked", "Blocked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(ManagedProject, related_name="webhook_events", on_delete=models.SET_NULL, null=True, blank=True)
    agent = models.ForeignKey(MachineAgent, related_name="webhook_events", on_delete=models.SET_NULL, null=True, blank=True)
    event_type = models.CharField(max_length=140, db_index=True)
    integration = models.CharField(max_length=120, blank=True, db_index=True)
    direction = models.CharField(max_length=16, choices=Direction.choices, default=Direction.INCOMING, db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RECEIVED, db_index=True)
    processing_time_ms = models.PositiveIntegerField(default=0)
    response_code = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    request_headers = models.JSONField(default=dict, blank=True)
    request_body = models.JSONField(default=dict, blank=True)
    response_headers = models.JSONField(default=dict, blank=True)
    response_body = models.JSONField(default=dict, blank=True)
    retry_history = models.JSONField(default=list, blank=True)
    execution_trace = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    signature_valid = models.BooleanField(default=True, db_index=True)
    threat_score = models.PositiveSmallIntegerField(default=0)
    ai_analysis = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["status", "-occurred_at"]),
            models.Index(fields=["integration", "event_type", "-occurred_at"]),
        ]


class AgentCommand(models.Model):
    class CommandType(models.TextChoices):
        RESTART = "restart", "Restart"
        BUILD = "build", "Build"
        DEPLOY = "deploy", "Deploy"
        ROLLBACK = "rollback", "Rollback"
        COLLECT_LOGS = "collect_logs", "Collect logs"
        REFRESH_DISCOVERY = "refresh_discovery", "Refresh discovery"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENT = "sent", "Sent"
        ACKNOWLEDGED = "acknowledged", "Acknowledged"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        EXPIRED = "expired", "Expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent = models.ForeignKey(MachineAgent, related_name="commands", on_delete=models.CASCADE)
    project = models.ForeignKey(ManagedProject, related_name="commands", on_delete=models.SET_NULL, null=True, blank=True)
    command_type = models.CharField(max_length=32, choices=CommandType.choices, db_index=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.QUEUED, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    result = models.JSONField(default=dict, blank=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="project_agent_commands", on_delete=models.SET_NULL, null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["agent", "status", "created_at"])]
