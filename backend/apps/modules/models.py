from django.db import models

from apps.core.models import UCEModel


class ConnectorDefinition(UCEModel):
    class ConnectionType(models.TextChoices):
        REST_API = "rest_api", "REST API"
        WEBHOOK = "webhook", "Webhook"
        DATABASE = "database", "Database"

    class AuthType(models.TextChoices):
        NONE = "none", "None"
        BEARER = "bearer", "Bearer"
        API_KEY = "api_key", "API Key"
        BASIC = "basic", "Basic"

    module_id = models.SlugField(unique=True)
    display_name = models.CharField(max_length=120)
    connection_type = models.CharField(max_length=30, choices=ConnectionType.choices)
    base_url = models.URLField(blank=True)
    auth_type = models.CharField(max_length=30, choices=AuthType.choices, default=AuthType.NONE)
    encrypted_credentials = models.TextField(blank=True)
    field_mappings = models.JSONField(default=dict)
    sync_frequency = models.PositiveIntegerField(default=300)
    health_status = models.CharField(max_length=30, default="unknown", db_index=True)

    class Meta:
        ordering = ["module_id"]
        indexes = [models.Index(fields=["module_id", "connection_type"])]

    def __str__(self):
        return self.display_name

