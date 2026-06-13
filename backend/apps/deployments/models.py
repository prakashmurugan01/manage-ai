from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.projects.models import Project, TimeStampedModel


class DeploymentControl(TimeStampedModel):
    class Environment(models.TextChoices):
        DEVELOPMENT = "development", "Development"
        STAGING = "staging", "Staging"
        PRODUCTION = "production", "Production"

    class Status(models.TextChoices):
        HEALTHY = "HEALTHY", "Healthy"
        DEGRADED = "DEGRADED", "Degraded"
        FAILED = "FAILED", "Failed"
        PAUSED = "PAUSED", "Paused"

    project = models.OneToOneField(Project, related_name="deployment", on_delete=models.CASCADE)
    environment = models.CharField(max_length=32, choices=Environment.choices, default=Environment.PRODUCTION)
    is_enabled = models.BooleanField(default=False)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PAUSED)
    version = models.CharField(max_length=80, blank=True)
    source_branch = models.CharField(max_length=120, blank=True)
    commit_sha = models.CharField(max_length=80, blank=True)
    last_deployed_at = models.DateTimeField(blank=True, null=True)
    toggled_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="deployment_toggles", on_delete=models.SET_NULL, blank=True, null=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["project__name"]

    def __str__(self):
        return f"{self.project.name} deployment"

    def set_enabled(self, enabled, user=None):
        self.is_enabled = enabled
        self.status = self.Status.HEALTHY if enabled else self.Status.PAUSED
        self.toggled_by = user
        if enabled:
            self.last_deployed_at = timezone.now()
        self.save()
        DeploymentHistory.objects.create(
            deployment=self,
            is_enabled=enabled,
            status=self.status,
            version=self.version,
            source_branch=self.source_branch,
            commit_sha=self.commit_sha,
            actor=user,
            notes=self.notes,
        )


class DeploymentHistory(TimeStampedModel):
    deployment = models.ForeignKey(DeploymentControl, related_name="history", on_delete=models.CASCADE)
    is_enabled = models.BooleanField()
    status = models.CharField(max_length=32)
    version = models.CharField(max_length=80, blank=True)
    source_branch = models.CharField(max_length=120, blank=True)
    commit_sha = models.CharField(max_length=80, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="deployment_history", on_delete=models.SET_NULL, blank=True, null=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]


class DeploymentRecord(TimeStampedModel):
    class Status(models.TextChoices):
        QUEUED = "QUEUED", "Queued"
        RUNNING = "RUNNING", "Running"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"

    project = models.ForeignKey(Project, related_name="deployment_records", on_delete=models.CASCADE)
    hosted_project = models.ForeignKey("hosting.HostedProject", related_name="deployment_records", on_delete=models.SET_NULL, blank=True, null=True)
    hosting_deployment = models.OneToOneField("hosting.DeploymentRun", related_name="deployment_record", on_delete=models.SET_NULL, blank=True, null=True)
    project_name = models.CharField(max_length=180)
    external_project_id = models.CharField(max_length=80, blank=True)
    client_name = models.CharField(max_length=180, blank=True)
    assigned_developer = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="assigned_deployment_records", on_delete=models.SET_NULL, blank=True, null=True)
    assigned_developer_name = models.CharField(max_length=180, blank=True)
    deployment_at = models.DateTimeField(default=timezone.now, db_index=True)
    hosting_provider = models.CharField(max_length=80, db_index=True)
    domain = models.CharField(max_length=255, blank=True, db_index=True)
    live_url = models.URLField(blank=True)
    server_details = models.JSONField(default=dict, blank=True)
    cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    renewal_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    expiry_date = models.DateField(blank=True, null=True, db_index=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.QUEUED, db_index=True)
    deployment_logs = models.JSONField(default=list, blank=True)
    pdf_documents = models.JSONField(default=list, blank=True)
    configuration_files = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="created_deployment_records", on_delete=models.SET_NULL, blank=True, null=True)

    class Meta:
        ordering = ["-deployment_at", "-created_at"]
        indexes = [
            models.Index(fields=["project", "-deployment_at"]),
            models.Index(fields=["hosting_provider", "status"]),
        ]

    def __str__(self):
        return f"{self.project_name} - {self.status}"
