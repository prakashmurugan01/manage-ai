from uuid import uuid4

from django.conf import settings
from django.db import models


class UCEModel(models.Model):
    id = models.UUIDField(default=uuid4, primary_key=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False, db_index=True)

    class Meta:
        abstract = True


class UniversalQuery(models.Model):
    class QueryType(models.TextChoices):
        SQL = "sql", "SQL"
        REST = "rest", "REST"
        NATURAL_LANGUAGE = "nl", "Natural Language"

    query_id = models.UUIDField(default=uuid4, primary_key=True, editable=False)
    raw_input = models.TextField()
    query_type = models.CharField(max_length=20, choices=QueryType.choices, db_index=True)
    normalized_iql = models.JSONField(default=dict)
    target_modules = models.JSONField(default=list)
    executed_at = models.DateTimeField(null=True, blank=True)
    execution_ms = models.IntegerField(null=True, blank=True)
    result_count = models.IntegerField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["query_type", "created_at"]),
            models.Index(fields=["created_by", "created_at"]),
        ]

    def __str__(self):
        return f"{self.query_type}: {self.raw_input[:80]}"


class ModuleRegistry(models.Model):
    module_id = models.SlugField(unique=True)
    display_name = models.CharField(max_length=100)
    version = models.CharField(max_length=20, default="1.0.0")
    schema = models.JSONField(default=dict)
    capabilities = models.JSONField(default=dict)
    endpoints = models.JSONField(default=list)
    is_active = models.BooleanField(default=True, db_index=True)
    last_health_check = models.DateTimeField(null=True, blank=True)
    health_status = models.CharField(max_length=30, default="unknown", db_index=True)
    registered_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["module_id"]
        indexes = [
            models.Index(fields=["module_id", "is_active"]),
            models.Index(fields=["health_status"]),
        ]

    def __str__(self):
        return self.display_name

