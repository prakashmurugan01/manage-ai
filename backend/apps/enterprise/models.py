import hashlib
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.permissions import Roles
from apps.projects.models import Project, TimeStampedModel


class Company(TimeStampedModel):
    name = models.CharField(max_length=180, unique=True)
    slug = models.SlugField(max_length=200, unique=True)
    domain = models.CharField(max_length=180, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="created_companies", on_delete=models.SET_NULL, blank=True, null=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class CompanyService(TimeStampedModel):
    company = models.ForeignKey(Company, related_name="services", on_delete=models.CASCADE)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    base_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    recurring_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["company__name", "name"]
        unique_together = ("company", "name")

    def __str__(self):
        return f"{self.company} - {self.name}"


class UniversalConnector(TimeStampedModel):
    class Category(models.TextChoices):
        CRM = "CRM", "CRM"
        ERP = "ERP", "ERP"
        HR = "HR", "HR"
        INVENTORY = "INVENTORY", "Inventory"
        PROJECT_MANAGEMENT = "PROJECT_MANAGEMENT", "Project Management"
        HOSTING = "HOSTING", "Hosting"
        SERVER = "SERVER", "Server"
        API = "API", "API"
        CUSTOM = "CUSTOM", "Custom"

    class Status(models.TextChoices):
        CONNECTED = "CONNECTED", "Connected"
        SYNCING = "SYNCING", "Syncing"
        DEGRADED = "DEGRADED", "Degraded"
        DISCONNECTED = "DISCONNECTED", "Disconnected"

    company = models.ForeignKey(Company, related_name="connectors", on_delete=models.CASCADE, blank=True, null=True)
    project = models.ForeignKey(Project, related_name="connectors", on_delete=models.SET_NULL, blank=True, null=True)
    name = models.CharField(max_length=180)
    category = models.CharField(max_length=40, choices=Category.choices, default=Category.CUSTOM)
    vendor = models.CharField(max_length=120, blank=True)
    endpoint_url = models.URLField(blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.DISCONNECTED)
    is_enabled = models.BooleanField(default=True)
    sync_interval_seconds = models.PositiveIntegerField(default=300)
    last_synced_at = models.DateTimeField(blank=True, null=True)
    last_error = models.TextField(blank=True)
    records_in = models.PositiveIntegerField(default=0)
    records_out = models.PositiveIntegerField(default=0)
    latency_ms = models.PositiveIntegerField(default=0)
    config = models.JSONField(default=dict, blank=True)
    ai_enhancement_enabled = models.BooleanField(default=False)

    class Meta:
        ordering = ["category", "name"]
        unique_together = ("company", "name", "category")

    def __str__(self):
        return f"{self.category} - {self.name}"

    def mark_synced(self, records_in=0, records_out=0, latency_ms=0):
        self.status = self.Status.CONNECTED
        self.last_synced_at = timezone.now()
        self.last_error = ""
        self.records_in += max(0, int(records_in))
        self.records_out += max(0, int(records_out))
        self.latency_ms = max(0, int(latency_ms))
        self.save(update_fields=["status", "last_synced_at", "last_error", "records_in", "records_out", "latency_ms", "updated_at"])
        return self


class ConnectionEvent(TimeStampedModel):
    class EventType(models.TextChoices):
        CREATED = "CREATED", "Created"
        SYNC_STARTED = "SYNC_STARTED", "Sync started"
        SYNC_COMPLETED = "SYNC_COMPLETED", "Sync completed"
        SYNC_FAILED = "SYNC_FAILED", "Sync failed"
        CONTROL = "CONTROL", "Control"
        DEPLOYMENT = "DEPLOYMENT", "Deployment"
        USER_ACTION = "USER_ACTION", "User action"

    company = models.ForeignKey(Company, related_name="connection_events", on_delete=models.CASCADE, blank=True, null=True)
    connector = models.ForeignKey(UniversalConnector, related_name="events", on_delete=models.CASCADE, blank=True, null=True)
    project = models.ForeignKey(Project, related_name="connection_events", on_delete=models.SET_NULL, blank=True, null=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="connection_events", on_delete=models.SET_NULL, blank=True, null=True)
    event_type = models.CharField(max_length=32, choices=EventType.choices)
    title = models.CharField(max_length=180)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class FeatureFlag(TimeStampedModel):
    class Dashboard(models.TextChoices):
        GLOBAL = "GLOBAL", "Global"
        SUPER_ADMIN = "SUPER_ADMIN", "Super Admin"
        ADMIN = "ADMIN", "Admin"
        DEVELOPER = "DEVELOPER", "Developer"
        CLIENT = "CLIENT", "Client"

    company = models.ForeignKey(Company, related_name="feature_flags", on_delete=models.CASCADE, blank=True, null=True)
    key = models.CharField(max_length=80)
    label = models.CharField(max_length=160)
    dashboard = models.CharField(max_length=32, choices=Dashboard.choices, default=Dashboard.GLOBAL)
    is_enabled = models.BooleanField(default=True)
    config = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["dashboard", "label"]
        unique_together = ("company", "key", "dashboard")

    def __str__(self):
        return f"{self.dashboard}: {self.label}"


class APIKey(TimeStampedModel):
    class Provider(models.TextChoices):
        OPENAI = "OPENAI", "OpenAI"
        META = "META", "Meta"
        OPEN_SOURCE = "OPEN_SOURCE", "Open source"
        OTHER = "OTHER", "Other"

    company = models.ForeignKey(Company, related_name="api_keys", on_delete=models.CASCADE, blank=True, null=True)
    name = models.CharField(max_length=160)
    provider = models.CharField(max_length=32, choices=Provider.choices, default=Provider.OTHER)
    key_hash = models.CharField(max_length=128)
    key_preview = models.CharField(max_length=40, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="created_api_keys", on_delete=models.SET_NULL, blank=True, null=True)

    class Meta:
        ordering = ["provider", "name"]

    def __str__(self):
        return f"{self.provider} - {self.name}"

    @staticmethod
    def hash_key(raw_key):
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    @staticmethod
    def preview_key(raw_key):
        if len(raw_key) <= 10:
            return "*" * len(raw_key)
        return f"{raw_key[:4]}...{raw_key[-4:]}"

    def set_raw_key(self, raw_key):
        self.key_hash = self.hash_key(raw_key)
        self.key_preview = self.preview_key(raw_key)


class APIKeyGrant(TimeStampedModel):
    api_key = models.ForeignKey(APIKey, related_name="grants", on_delete=models.CASCADE)
    developer = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="api_key_grants", on_delete=models.CASCADE)
    can_view = models.BooleanField(default=True)
    can_use = models.BooleanField(default=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    granted_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="issued_api_key_grants", on_delete=models.SET_NULL, blank=True, null=True)

    class Meta:
        ordering = ["api_key__name", "developer__email"]
        unique_together = ("api_key", "developer")

    @property
    def is_valid(self):
        return self.can_use and self.api_key.is_active and (not self.expires_at or self.expires_at > timezone.now())

    def __str__(self):
        return f"{self.api_key} -> {self.developer}"


class ProjectEstimate(TimeStampedModel):
    class Status(models.TextChoices):
        REQUESTED = "REQUESTED", "Requested"
        DRAFT = "DRAFT", "Draft"
        SENT = "SENT", "Sent"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    company = models.ForeignKey(Company, related_name="estimates", on_delete=models.CASCADE, blank=True, null=True)
    project = models.ForeignKey(Project, related_name="estimates", on_delete=models.SET_NULL, blank=True, null=True)
    client = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="project_estimates", on_delete=models.CASCADE)
    title = models.CharField(max_length=180)
    scope = models.TextField()
    features = models.JSONField(default=list, blank=True)
    timeline_days = models.PositiveIntegerField(default=30)
    development_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    hosting_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    maintenance_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=12, default="USD")
    demo_url = models.URLField(blank=True)
    demo_notes = models.TextField(blank=True)
    ui_preview = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.DRAFT)
    sent_at = models.DateTimeField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="created_project_estimates", on_delete=models.SET_NULL, blank=True, null=True)

    class Meta:
        ordering = ["-updated_at"]

    @property
    def total_cost(self):
        return self.development_cost + self.hosting_cost + self.maintenance_cost

    def mark_sent(self):
        self.status = self.Status.SENT
        self.sent_at = timezone.now()
        self.save(update_fields=["status", "sent_at", "updated_at"])

    def __str__(self):
        return self.title


class EmailEvent(TimeStampedModel):
    class Status(models.TextChoices):
        QUEUED = "QUEUED", "Queued"
        SENT = "SENT", "Sent"
        FAILED = "FAILED", "Failed"

    company = models.ForeignKey(Company, related_name="email_events", on_delete=models.SET_NULL, blank=True, null=True)
    recipient = models.EmailField()
    subject = models.CharField(max_length=220)
    body = models.TextField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    error = models.TextField(blank=True)
    sent_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.subject} -> {self.recipient}"


class HostingConnection(TimeStampedModel):
    class Provider(models.TextChoices):
        AWS = "AWS", "AWS"
        AZURE = "AZURE", "Azure"
        GCP = "GCP", "Google Cloud"
        DIGITALOCEAN = "DIGITALOCEAN", "DigitalOcean"
        VERCEL = "VERCEL", "Vercel"
        NETLIFY = "NETLIFY", "Netlify"
        CUSTOM = "CUSTOM", "Custom"

    class Status(models.TextChoices):
        CONNECTED = "CONNECTED", "Connected"
        DEGRADED = "DEGRADED", "Degraded"
        DISCONNECTED = "DISCONNECTED", "Disconnected"

    company = models.ForeignKey(Company, related_name="hosting_connections", on_delete=models.CASCADE, blank=True, null=True)
    project = models.ForeignKey(Project, related_name="hosting_connections", on_delete=models.CASCADE, blank=True, null=True)
    provider = models.CharField(max_length=32, choices=Provider.choices, default=Provider.CUSTOM)
    name = models.CharField(max_length=160)
    endpoint_url = models.URLField(blank=True)
    is_enabled = models.BooleanField(default=False)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.DISCONNECTED)
    region = models.CharField(max_length=80, blank=True)
    last_deployed_at = models.DateTimeField(blank=True, null=True)
    config = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["provider", "name"]

    def __str__(self):
        return f"{self.provider} - {self.name}"


class ServerControlState(TimeStampedModel):
    class Health(models.TextChoices):
        STABLE = "STABLE", "Stable"
        SCALING = "SCALING", "Scaling"
        OVERLOADED = "OVERLOADED", "Overloaded"
        OFFLINE = "OFFLINE", "Offline"

    company = models.OneToOneField(Company, related_name="server_control", on_delete=models.CASCADE, blank=True, null=True)
    is_enabled = models.BooleanField(default=True)
    health = models.CharField(max_length=32, choices=Health.choices, default=Health.STABLE)
    scale_units = models.PositiveSmallIntegerField(default=1)
    storage_total_gb = models.DecimalField(max_digits=10, decimal_places=2, default=500)
    storage_used_gb = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    file_count = models.PositiveIntegerField(default=0)
    active_users = models.PositiveIntegerField(default=0)
    incoming_requests = models.PositiveIntegerField(default=0)
    outgoing_requests = models.PositiveIntegerField(default=0)
    uptime_seconds = models.PositiveBigIntegerField(default=0)
    last_checked_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["company__name"]

    def __str__(self):
        return f"Server {self.company or 'Global'}"

    def rotate_live_metrics(self):
        seed = secrets.randbelow(100)
        self.active_users = max(1, self.active_users + (seed % 5) - 2)
        self.incoming_requests += 8 + seed
        self.outgoing_requests += 5 + seed // 2
        self.uptime_seconds += max(1, int((timezone.now() - self.last_checked_at).total_seconds()))
        self.last_checked_at = timezone.now()
        if not self.is_enabled:
            self.health = self.Health.OFFLINE
        elif self.scale_units > 3 or self.active_users > 80:
            self.health = self.Health.SCALING
        else:
            self.health = self.Health.STABLE
        self.save()
        return self


class NetworkTelemetry(TimeStampedModel):
    company = models.ForeignKey(Company, related_name="network_telemetry", on_delete=models.CASCADE, blank=True, null=True)
    upload_mbps = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    download_mbps = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    latency_ms = models.PositiveIntegerField(default=0)
    packet_loss_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    requests_per_second = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    health_score = models.PositiveSmallIntegerField(default=100)
    source = models.CharField(max_length=80, default="platform-agent")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Network {self.company or 'Global'} - {self.latency_ms}ms"


class VoiceCommandIntent(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        DISABLED = "DISABLED", "Disabled"

    company = models.ForeignKey(Company, related_name="voice_intents", on_delete=models.CASCADE, blank=True, null=True)
    phrase = models.CharField(max_length=180)
    action = models.CharField(max_length=120)
    target_module = models.CharField(max_length=80)
    minimum_role = models.CharField(max_length=32, default=Roles.ADMIN)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    config = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["target_module", "phrase"]
        unique_together = ("company", "phrase", "target_module")

    def __str__(self):
        return f"{self.phrase} -> {self.action}"


class CollaborationChannel(TimeStampedModel):
    company = models.ForeignKey(Company, related_name="collaboration_channels", on_delete=models.CASCADE, blank=True, null=True)
    project = models.ForeignKey(Project, related_name="collaboration_channels", on_delete=models.CASCADE, blank=True, null=True)
    name = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="collaboration_channels", blank=True)
    is_team_bot_enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("company", "project", "name")

    def __str__(self):
        return self.name


class CollaborationMessage(TimeStampedModel):
    class Kind(models.TextChoices):
        MESSAGE = "MESSAGE", "Message"
        FILE = "FILE", "File"
        CONFIG = "CONFIG", "Config"
        BOT = "BOT", "Bot"

    channel = models.ForeignKey(CollaborationChannel, related_name="messages", on_delete=models.CASCADE)
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="collaboration_messages", on_delete=models.SET_NULL, blank=True, null=True)
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.MESSAGE)
    ciphertext = models.TextField()
    nonce = models.CharField(max_length=120, blank=True)
    sender_public_key = models.TextField(blank=True)
    attachment = models.FileField(upload_to="collaboration/%Y/%m/", blank=True)
    attachment_name = models.CharField(max_length=220, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.kind} in {self.channel_id}"


class SystemModuleControl(TimeStampedModel):
    """Controls which system modules are enabled/disabled globally or per company"""

    class Module(models.TextChoices):
        TASKS = "TASKS", "Tasks"
        COLLABORATION = "COLLABORATION", "Collaboration"
        TICKETS = "TICKETS", "Tickets"
        NOTIFICATIONS = "NOTIFICATIONS", "Notifications"
        AI_CHATBOT = "AI_CHATBOT", "AI Chatbot"
        MONITORING = "MONITORING", "Monitoring"
        CONNECTION_ENGINE = "CONNECTION_ENGINE", "Connection Engine"
        PROJECT_FILES = "PROJECT_FILES", "Project Files"
        ANALYTICS = "ANALYTICS", "Analytics"
        AUDIT = "AUDIT", "Audit Logs"

    company = models.ForeignKey(Company, related_name="module_controls", on_delete=models.CASCADE, blank=True, null=True)
    module = models.CharField(max_length=32, choices=Module.choices)
    is_enabled = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="module_control_changes", on_delete=models.SET_NULL, blank=True, null=True)
    changed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["module"]
        unique_together = ("company", "module")

    def __str__(self):
        return f"{self.module} - {'Enabled' if self.is_enabled else 'Disabled'}"


class UserAccessControl(TimeStampedModel):
    """Fine-grained role-based access control per user and module"""

    class Action(models.TextChoices):
        VIEW = "VIEW", "View"
        CREATE = "CREATE", "Create"
        EDIT = "EDIT", "Edit"
        DELETE = "DELETE", "Delete"
        ADMIN = "ADMIN", "Admin"
        EXPORT = "EXPORT", "Export"

    company = models.ForeignKey(Company, related_name="access_controls", on_delete=models.CASCADE, blank=True, null=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="access_controls", on_delete=models.CASCADE)
    module = models.CharField(max_length=32, choices=SystemModuleControl.Module.choices)
    role = models.CharField(max_length=32, choices=[
        (Roles.SUPER_ADMIN, "Super Admin"),
        (Roles.ADMIN, "Admin"),
        (Roles.DEVELOPER, "Developer"),
        (Roles.CLIENT, "Client"),
    ])
    actions = models.JSONField(default=list, blank=True, help_text="List of allowed actions")
    is_enabled = models.BooleanField(default=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    granted_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="issued_access_controls", on_delete=models.SET_NULL, blank=True, null=True)

    class Meta:
        ordering = ["user__email", "module"]
        unique_together = ("user", "module")

    @property
    def is_valid(self):
        return self.is_enabled and (not self.expires_at or self.expires_at > timezone.now())

    def __str__(self):
        return f"{self.user.email} - {self.module}"


class AuthenticationSettings(TimeStampedModel):
    """Controls authentication behavior and options"""

    class LoginMethod(models.TextChoices):
        EMAIL = "EMAIL", "Email"
        FACE = "FACE", "Face Recognition"
        BOTH = "BOTH", "Both"

    company = models.OneToOneField(Company, related_name="auth_settings", on_delete=models.CASCADE)
    allow_password_change = models.BooleanField(default=True)
    allow_forgot_password = models.BooleanField(default=True)
    allow_face_login = models.BooleanField(default=False)
    default_login_method = models.CharField(max_length=32, choices=LoginMethod.choices, default=LoginMethod.EMAIL)
    password_expiry_days = models.PositiveSmallIntegerField(default=90, help_text="0 means no expiry")
    min_password_length = models.PositiveSmallIntegerField(default=8)
    require_2fa = models.BooleanField(default=False)
    session_timeout_minutes = models.PositiveSmallIntegerField(default=60)

    admin_login_methods = models.JSONField(default=list, blank=True, help_text="Login methods allowed for admins")
    developer_login_methods = models.JSONField(default=list, blank=True)
    client_login_methods = models.JSONField(default=list, blank=True)

    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="updated_auth_settings", on_delete=models.SET_NULL, blank=True, null=True)

    class Meta:
        verbose_name_plural = "Authentication Settings"

    def __str__(self):
        return f"Auth Settings for {self.company}"


class CloudStorageSettings(TimeStampedModel):
    """Manages cloud storage integration and access"""

    class Provider(models.TextChoices):
        AWS_S3 = "AWS_S3", "AWS S3"
        AZURE_BLOB = "AZURE_BLOB", "Azure Blob Storage"
        GCP_STORAGE = "GCP_STORAGE", "Google Cloud Storage"
        LOCAL = "LOCAL", "Local Storage"

    company = models.OneToOneField(Company, related_name="storage_settings", on_delete=models.CASCADE)
    provider = models.CharField(max_length=32, choices=Provider.choices, default=Provider.LOCAL)
    is_enabled = models.BooleanField(default=True)
    endpoint_url = models.URLField(blank=True)
    bucket_name = models.CharField(max_length=180, blank=True)
    access_key_hash = models.CharField(max_length=128, blank=True)
    storage_limit_gb = models.DecimalField(max_digits=10, decimal_places=2, default=100)
    current_usage_gb = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    file_count = models.PositiveIntegerField(default=0)
    is_backup_enabled = models.BooleanField(default=True)
    last_backup_at = models.DateTimeField(blank=True, null=True)
    config = models.JSONField(default=dict, blank=True)

    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="updated_storage_settings", on_delete=models.SET_NULL, blank=True, null=True)

    class Meta:
        verbose_name_plural = "Cloud Storage Settings"

    def __str__(self):
        return f"Storage for {self.company}"

    @property
    def usage_percent(self):
        if self.storage_limit_gb == 0:
            return 0
        return round((float(self.current_usage_gb) / float(self.storage_limit_gb)) * 100, 2)


class ServerFileAccess(TimeStampedModel):
    """Logs and tracks server file access by admins"""

    class AccessType(models.TextChoices):
        BROWSE = "BROWSE", "Browse"
        VIEW = "VIEW", "View"
        DOWNLOAD = "DOWNLOAD", "Download"
        UPLOAD = "UPLOAD", "Upload"

    company = models.ForeignKey(Company, related_name="file_accesses", on_delete=models.CASCADE, blank=True, null=True)
    accessed_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="file_accesses", on_delete=models.SET_NULL, blank=True, null=True)
    file_path = models.CharField(max_length=500)
    file_name = models.CharField(max_length=220, blank=True)
    file_size_bytes = models.PositiveIntegerField(default=0)
    access_type = models.CharField(max_length=16, choices=AccessType.choices)
    is_success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.accessed_by} - {self.file_path}"


class SystemSettingsAuditLog(TimeStampedModel):
    """Comprehensive audit log for all settings changes"""

    class EntityType(models.TextChoices):
        MODULE_CONTROL = "MODULE_CONTROL", "Module Control"
        ACCESS_CONTROL = "ACCESS_CONTROL", "Access Control"
        AUTH_SETTINGS = "AUTH_SETTINGS", "Auth Settings"
        STORAGE_SETTINGS = "STORAGE_SETTINGS", "Storage Settings"
        API_KEY = "API_KEY", "API Key"
        FEATURE_FLAG = "FEATURE_FLAG", "Feature Flag"

    company = models.ForeignKey(Company, related_name="settings_audit_logs", on_delete=models.CASCADE, blank=True, null=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="settings_changes", on_delete=models.SET_NULL, blank=True, null=True)
    entity_type = models.CharField(max_length=32, choices=EntityType.choices)
    entity_id = models.PositiveIntegerField()
    action = models.CharField(max_length=32, choices=[
        ("CREATE", "Created"),
        ("UPDATE", "Updated"),
        ("DELETE", "Deleted"),
        ("ENABLE", "Enabled"),
        ("DISABLE", "Disabled"),
    ])
    old_values = models.JSONField(default=dict, blank=True)
    new_values = models.JSONField(default=dict, blank=True)
    change_summary = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["company", "-created_at"])]

    def __str__(self):
        return f"{self.entity_type} {self.action} by {self.changed_by}"
