import uuid

from django.db import models


class ApiKey(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        EDITOR = "editor", "Editor"
        CLIENT = "client", "Client (Legacy)"
        VIEWER = "viewer", "Viewer"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey("projects.Project", related_name="uce_api_keys", on_delete=models.CASCADE)
    name = models.CharField(max_length=160)
    key_encrypted = models.TextField()
    key_hash = models.CharField(max_length=256, blank=True, db_index=True)
    key_prefix = models.CharField(max_length=8, db_index=True)
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.VIEWER)
    rate_limit_per_minute = models.PositiveIntegerField(default=100)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    ip_whitelist = models.JSONField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["project__name", "name"]

    def __str__(self):
        return f"{self.project}: {self.name}"


class ApiKeyUsageLog(models.Model):
    api_key = models.ForeignKey(ApiKey, related_name="usage_logs", on_delete=models.SET_NULL, null=True)
    endpoint = models.CharField(max_length=500)
    http_method = models.CharField(max_length=12)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    response_code = models.PositiveIntegerField(default=200)
    response_time_ms = models.PositiveIntegerField(default=0)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [models.Index(fields=["api_key", "-timestamp"])]
