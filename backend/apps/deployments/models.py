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
