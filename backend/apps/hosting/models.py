from django.conf import settings
from django.db import models
from django.utils import timezone
import uuid


class HostedProject(models.Model):
    class Platform(models.TextChoices):
        VERCEL = "vercel", "Vercel"
        RAILWAY = "railway", "Railway"
        AWS = "aws", "AWS"
        S3 = "s3", "AWS S3"
        CLOUDFRONT = "cloudfront", "AWS CloudFront"
        NETLIFY = "netlify", "Netlify"
        DIGITALOCEAN = "digitalocean", "DigitalOcean"
        CLOUDWAYS = "cloudways", "Cloudways"
        HOSTINGER = "hostinger", "Hostinger"
        SCALAHOSTING = "scalahosting", "ScalaHosting"
        SITEGROUND = "siteground", "SiteGround"
        BLUEHOST = "bluehost", "Bluehost"
        GODADDY = "godaddy", "GoDaddy"
        HOSTGATOR = "hostgator", "HostGator"
        CYBERIN = "cyberin", "Cyberin"
        HOSTINGRAJA = "hostingraja", "HostingRaja"
        BIGROCK = "bigrock", "BigRock"
        HOSTING_HOME = "hosting_home", "Hosting Home"
        CUSTOM = "custom", "Custom"

    class Status(models.TextChoices):
        LIVE = "live", "Live"
        EXPIRED = "expired", "Expired"
        PENDING = "pending", "Pending"
        SUSPENDED = "suspended", "Suspended"
        MAINTENANCE = "maintenance", "Maintenance"

    class ServerStatus(models.TextChoices):
        ONLINE = "online", "Online"
        OFFLINE = "offline", "Offline"
        SLOW = "slow", "Slow"
        UNKNOWN = "unknown", "Unknown"

    client = models.ForeignKey("crm.Company", related_name="hosted_projects", on_delete=models.SET_NULL, null=True, blank=True)
    client_name = models.CharField(max_length=180, blank=True, db_index=True)
    name = models.CharField(max_length=180)
    domain = models.CharField(max_length=255, unique=True)
    hosting_platform = models.CharField(max_length=32, choices=Platform.choices, default=Platform.CUSTOM)
    deploy_url = models.URLField(blank=True)
    server_ip = models.GenericIPAddressField(null=True, blank=True)
    access_key_encrypted = models.TextField(blank=True)
    access_key_prefix = models.CharField(max_length=12, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDING, db_index=True)
    tag = models.CharField(max_length=32, default="active", db_index=True)
    link_is_active = models.BooleanField(default=True)
    server_status = models.CharField(max_length=24, choices=ServerStatus.choices, default=ServerStatus.UNKNOWN, db_index=True)
    response_time_ms = models.PositiveIntegerField(default=0)
    uptime_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    check_interval_seconds = models.PositiveIntegerField(default=60)
    downtime_count = models.PositiveIntegerField(default=0)
    start_date = models.DateField(default=timezone.localdate)
    expiry_date = models.DateField(db_index=True)
    monthly_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["expiry_date", "name"]

    def __str__(self):
        return self.name

    @property
    def display_client_name(self):
        return self.client.name if self.client else self.client_name


class HostingLifecycle(models.Model):
    class Event(models.TextChoices):
        CREATED = "created", "Created"
        UPDATED = "updated", "Updated"
        RENEWED = "renewed", "Renewed"
        SUSPENDED = "suspended", "Suspended"
        REACTIVATED = "reactivated", "Reactivated"
        EXPIRED = "expired", "Expired"
        PLATFORM_CHANGED = "platform_changed", "Platform changed"
        HEALTH_CHECK = "health_check", "Health check"
        LINK_DISABLED = "link_disabled", "Link disabled"
        LINK_ENABLED = "link_enabled", "Link enabled"
        FAILOVER = "failover", "Failover"
        PROVIDER_SYNCED = "provider_synced", "Provider synced"
        PROVIDER_TOGGLED = "provider_toggled", "Provider toggled"
        EMAIL_CREATED = "email_created", "Email created"
        EMAIL_DELETED = "email_deleted", "Email deleted"
        EMAIL_CHECK = "email_check", "Email check"
        DOMAIN_CHECK = "domain_check", "Domain check"
        VERCEL_SYNCED = "vercel_synced", "Vercel synced"
        VERCEL_REDEPLOY = "vercel_redeploy", "Vercel redeploy"
        ARCHIVED = "archived", "Archived"
        RESTORED = "restored", "Restored"
        API_KEY_CREATED = "api_key_created", "API key created"

    project = models.ForeignKey(HostedProject, related_name="lifecycle", on_delete=models.CASCADE)
    event_type = models.CharField(max_length=32, choices=Event.choices)
    old_expiry = models.DateField(null=True, blank=True)
    new_expiry = models.DateField(null=True, blank=True)
    old_platform = models.CharField(max_length=32, blank=True)
    new_platform = models.CharField(max_length=32, blank=True)
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="hosting_events", on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]


class HostingProjectApiKey(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        CLIENT = "client", "Client"

    class Permission(models.TextChoices):
        READ = "read", "Read"
        WRITE = "write", "Write"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(HostedProject, related_name="api_keys", on_delete=models.CASCADE)
    name = models.CharField(max_length=160)
    key_encrypted = models.TextField()
    key_prefix = models.CharField(max_length=12, db_index=True)
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.CLIENT)
    permission_level = models.CharField(max_length=16, choices=Permission.choices, default=Permission.READ)
    rate_limit_per_minute = models.PositiveIntegerField(default=60)
    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="hosting_api_keys", on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["project__name", "name"]

    def __str__(self):
        return f"{self.project} - {self.name}"


class HostingApiUsageLog(models.Model):
    api_key = models.ForeignKey(HostingProjectApiKey, related_name="usage_logs", on_delete=models.SET_NULL, null=True)
    endpoint = models.CharField(max_length=500)
    http_method = models.CharField(max_length=12)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    response_code = models.PositiveIntegerField(default=200)
    response_time_ms = models.PositiveIntegerField(default=0)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [models.Index(fields=["api_key", "-timestamp"])]


class HostingProvider(models.Model):
    class Provider(models.TextChoices):
        AWS = "aws", "AWS"
        AWS_S3 = "aws_s3", "AWS S3"
        AWS_CLOUDFRONT = "aws_cloudfront", "AWS CloudFront"
        NETLIFY = "netlify", "Netlify"
        DIGITALOCEAN = "digitalocean", "DigitalOcean"
        CLOUDWAYS = "cloudways", "Cloudways"
        HOSTINGER = "hostinger", "Hostinger"
        SCALAHOSTING = "scalahosting", "ScalaHosting"
        SITEGROUND = "siteground", "SiteGround"
        BLUEHOST = "bluehost", "Bluehost"
        GODADDY = "godaddy", "GoDaddy"
        HOSTGATOR = "hostgator", "HostGator"
        CYBERIN = "cyberin", "Cyberin"
        HOSTINGRAJA = "hostingraja", "HostingRaja"
        BIGROCK = "bigrock", "BigRock"
        HOSTING_HOME = "hosting_home", "Hosting Home"
        VERCEL = "vercel", "Vercel"

    name = models.CharField(max_length=120)
    provider = models.CharField(max_length=24, choices=Provider.choices, db_index=True)
    priority = models.PositiveSmallIntegerField(default=4, db_index=True)
    is_enabled = models.BooleanField(default=True)
    config = models.JSONField(default=dict, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority", "provider", "name"]
        unique_together = [("provider", "name")]

    def __str__(self):
        return f"{self.get_provider_display()} - {self.name}"


class HostingLink(models.Model):
    class Provider(models.TextChoices):
        AWS = "aws", "AWS"
        AWS_S3 = "aws_s3", "AWS S3"
        AWS_CLOUDFRONT = "aws_cloudfront", "AWS CloudFront"
        NETLIFY = "netlify", "Netlify"
        DIGITALOCEAN = "digitalocean", "DigitalOcean"
        CLOUDWAYS = "cloudways", "Cloudways"
        HOSTINGER = "hostinger", "Hostinger"
        SCALAHOSTING = "scalahosting", "ScalaHosting"
        SITEGROUND = "siteground", "SiteGround"
        BLUEHOST = "bluehost", "Bluehost"
        GODADDY = "godaddy", "GoDaddy"
        HOSTGATOR = "hostgator", "HostGator"
        CYBERIN = "cyberin", "Cyberin"
        HOSTINGRAJA = "hostingraja", "HostingRaja"
        BIGROCK = "bigrock", "BigRock"
        HOSTING_HOME = "hosting_home", "Hosting Home"
        VERCEL = "vercel", "Vercel"

    class ServerType(models.TextChoices):
        SHARED = "shared", "Shared"
        VPS = "vps", "VPS"
        CLOUD = "cloud", "Cloud"
        MANAGED = "managed", "Managed"
        WORDPRESS = "wordpress", "WordPress"
        EMAIL = "email", "Email"
        STATIC = "static", "Static"

    class LinkTag(models.TextChoices):
        PRODUCTION = "production", "Production"
        STAGING = "staging", "Staging"
        BACKUP = "backup", "Backup"
        PRIMARY = "primary", "Primary"
        SECONDARY = "secondary", "Secondary"

    class Status(models.TextChoices):
        ON = "on", "On"
        OFF = "off", "Off"
        BUILDING = "building", "Building"
        ERROR = "error", "Error"
        UNKNOWN = "unknown", "Unknown"

    class Health(models.TextChoices):
        HEALTHY = "healthy", "Healthy"
        DEGRADED = "degraded", "Degraded"
        DOWN = "down", "Down"
        UNKNOWN = "unknown", "Unknown"

    project = models.ForeignKey(HostedProject, related_name="hosting_links", on_delete=models.CASCADE)
    provider_config = models.ForeignKey(HostingProvider, related_name="links", on_delete=models.SET_NULL, null=True, blank=True)
    provider = models.CharField(max_length=24, choices=Provider.choices, db_index=True)
    priority = models.PositiveSmallIntegerField(default=4, db_index=True)
    server_type = models.CharField(max_length=24, choices=ServerType.choices, default=ServerType.CLOUD, db_index=True)
    tag = models.CharField(max_length=24, choices=LinkTag.choices, default=LinkTag.PRODUCTION, db_index=True)
    label = models.CharField(max_length=160, blank=True)
    url = models.URLField(blank=True)
    domain = models.CharField(max_length=255, blank=True, db_index=True)
    external_id = models.CharField(max_length=180, blank=True, db_index=True)
    region = models.CharField(max_length=80, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UNKNOWN, db_index=True)
    health_status = models.CharField(max_length=20, choices=Health.choices, default=Health.UNKNOWN, db_index=True)
    is_active = models.BooleanField(default=False, db_index=True)
    is_enabled = models.BooleanField(default=True)
    response_time_ms = models.PositiveIntegerField(default=0)
    uptime_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    last_http_status = models.PositiveIntegerField(null=True, blank=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    last_failover_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["project__name", "priority", "provider", "label"]
        indexes = [models.Index(fields=["project", "priority", "health_status"], name="hosting_hos_project_5ff445_idx")]

    def __str__(self):
        return f"{self.project} - {self.provider} - {self.label or self.domain or self.external_id}"


class EmailAccount(models.Model):
    class Provider(models.TextChoices):
        CPANEL = "cpanel", "cPanel"
        HOSTINGER = "hostinger", "Hostinger"
        SITEGROUND = "siteground", "SiteGround"
        BLUEHOST = "bluehost", "Bluehost"
        GODADDY = "godaddy", "GoDaddy"
        HOSTGATOR = "hostgator", "HostGator"
        BIGROCK = "bigrock", "BigRock"
        GOOGLE_WORKSPACE = "google_workspace", "Google Workspace"
        MICROSOFT_365 = "microsoft_365", "Microsoft 365"
        CUSTOM = "custom", "Custom"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        DISABLED = "disabled", "Disabled"
        SUSPENDED = "suspended", "Suspended"
        MISCONFIGURED = "misconfigured", "Misconfigured"

    project = models.ForeignKey(HostedProject, related_name="email_accounts", on_delete=models.CASCADE)
    hosting_link = models.ForeignKey(HostingLink, related_name="email_accounts", on_delete=models.SET_NULL, null=True, blank=True)
    provider = models.CharField(max_length=32, choices=Provider.choices, default=Provider.CPANEL, db_index=True)
    email = models.EmailField(db_index=True)
    display_name = models.CharField(max_length=160, blank=True)
    quota_mb = models.PositiveIntegerField(default=1024)
    used_mb = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    mx_status = models.CharField(max_length=24, default="unknown", db_index=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["project__name", "email"]
        unique_together = [("project", "email")]

    def __str__(self):
        return self.email


class DomainStatus(models.Model):
    class Health(models.TextChoices):
        HEALTHY = "healthy", "Healthy"
        WARNING = "warning", "Warning"
        CRITICAL = "critical", "Critical"
        UNKNOWN = "unknown", "Unknown"

    project = models.OneToOneField(HostedProject, related_name="domain_status", on_delete=models.CASCADE)
    domain = models.CharField(max_length=255, db_index=True)
    mx_records = models.JSONField(default=list, blank=True)
    mx_status = models.CharField(max_length=24, choices=Health.choices, default=Health.UNKNOWN, db_index=True)
    ssl_status = models.CharField(max_length=24, choices=Health.choices, default=Health.UNKNOWN, db_index=True)
    ssl_expires_at = models.DateTimeField(null=True, blank=True)
    domain_expires_at = models.DateField(null=True, blank=True)
    email_health_score = models.PositiveSmallIntegerField(default=0)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["domain"]

    def __str__(self):
        return self.domain


def deployment_upload_path(instance, filename):
    return f"hosting_uploads/{instance.id}/{filename}"


class ProjectUpload(models.Model):
    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        PROCESSING = "processing", "Processing"
        ANALYZED = "analyzed", "Analyzed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="hosting_uploads", on_delete=models.SET_NULL, null=True, blank=True)
    project = models.ForeignKey(HostedProject, related_name="uploads", on_delete=models.SET_NULL, null=True, blank=True)
    original_name = models.CharField(max_length=255)
    upload = models.FileField(upload_to=deployment_upload_path)
    size_bytes = models.PositiveBigIntegerField(default=0)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.UPLOADED, db_index=True)
    project_type = models.CharField(max_length=40, blank=True, db_index=True)
    detected_stack = models.JSONField(default=list, blank=True)
    suggested_providers = models.JSONField(default=list, blank=True)
    analysis = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    analyzed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.original_name


class DeploymentRun(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        UPLOADING = "uploading", "Uploading"
        BUILDING = "building", "Building"
        DEPLOYING = "deploying", "Deploying"
        LIVE = "live", "Live"
        ERROR = "error", "Error"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    upload = models.ForeignKey(ProjectUpload, related_name="deployments", on_delete=models.CASCADE)
    project = models.ForeignKey(HostedProject, related_name="deployment_runs", on_delete=models.SET_NULL, null=True, blank=True)
    primary_provider = models.CharField(max_length=32, default="vercel", db_index=True)
    backup_provider = models.CharField(max_length=32, blank=True)
    domain = models.CharField(max_length=255, blank=True)
    build_command = models.CharField(max_length=255, blank=True)
    output_directory = models.CharField(max_length=160, blank=True)
    environment = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.QUEUED, db_index=True)
    live_url = models.URLField(blank=True)
    logs = models.JSONField(default=list, blank=True)
    progress = models.PositiveSmallIntegerField(default=0)
    error_message = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="hosting_deployments", on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.upload.original_name} - {self.status}"


class HostingFailoverState(models.Model):
    project = models.OneToOneField(HostedProject, related_name="failover_state", on_delete=models.CASCADE)
    active_link = models.ForeignKey(HostingLink, related_name="active_for_projects", on_delete=models.SET_NULL, null=True, blank=True)
    failover_enabled = models.BooleanField(default=True)
    last_reason = models.TextField(blank=True)
    last_evaluated_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["project__name"]


class VercelProject(models.Model):
    hosted_project = models.OneToOneField(HostedProject, related_name="vercel_project", on_delete=models.CASCADE, null=True, blank=True)
    vercel_id = models.CharField(max_length=80, unique=True, db_index=True)
    name = models.CharField(max_length=180, db_index=True)
    account_id = models.CharField(max_length=120, blank=True)
    team_id = models.CharField(max_length=120, blank=True)
    framework = models.CharField(max_length=80, blank=True)
    production_domain = models.CharField(max_length=255, blank=True)
    latest_deployment_id = models.CharField(max_length=120, blank=True)
    latest_deployment_url = models.URLField(blank=True)
    latest_deployment_status = models.CharField(max_length=40, blank=True, db_index=True)
    raw = models.JSONField(default=dict, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class VercelProjectLink(models.Model):
    class Tag(models.TextChoices):
        PRIMARY = "primary", "Primary"
        BACKUP = "backup", "Backup"
        TESTING = "testing", "Testing"
        PREVIEW = "preview", "Preview"
        CUSTOM = "custom", "Custom"

    project = models.ForeignKey(VercelProject, related_name="links", on_delete=models.CASCADE)
    domain = models.CharField(max_length=255, db_index=True)
    url = models.URLField()
    tag = models.CharField(max_length=20, choices=Tag.choices, default=Tag.CUSTOM, db_index=True)
    is_active = models.BooleanField(default=True)
    disabled_at = models.DateTimeField(null=True, blank=True)
    last_http_status = models.PositiveIntegerField(null=True, blank=True)
    response_time_ms = models.PositiveIntegerField(default=0)
    uptime_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["project__name", "tag", "domain"]
        unique_together = [("project", "domain")]

    def __str__(self):
        return f"{self.project} - {self.domain}"


class VercelDeployment(models.Model):
    project = models.ForeignKey(VercelProject, related_name="deployments", on_delete=models.CASCADE)
    deployment_id = models.CharField(max_length=120, unique=True, db_index=True)
    url = models.URLField(blank=True)
    status = models.CharField(max_length=40, db_index=True)
    target = models.CharField(max_length=40, blank=True)
    meta = models.JSONField(default=dict, blank=True)
    inspector_url = models.URLField(blank=True)
    error_message = models.TextField(blank=True)
    created_at_vercel = models.DateTimeField(null=True, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    raw = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at_vercel", "-id"]

    def __str__(self):
        return f"{self.project} - {self.status}"


class HostingStatus(models.Model):
    class Mode(models.TextChoices):
        ACTIVE = "active", "Active"
        DISABLED = "disabled", "Disabled"

    project = models.OneToOneField(VercelProject, related_name="hosting_status", on_delete=models.CASCADE)
    is_enabled = models.BooleanField(default=True, db_index=True)
    mode = models.CharField(max_length=20, choices=Mode.choices, default=Mode.ACTIVE)
    disabled_redirect_url = models.URLField(blank=True)
    disabled_reason = models.TextField(blank=True)
    last_action_at = models.DateTimeField(null=True, blank=True)
    last_action_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="vercel_hosting_actions", on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name_plural = "hosting statuses"
