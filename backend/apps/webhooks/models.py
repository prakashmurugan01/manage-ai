from django.db import models

from apps.core.models import UCEModel


class Event(UCEModel):
    event_type = models.CharField(max_length=100, db_index=True)
    source_module = models.CharField(max_length=50, db_index=True)
    entity_type = models.CharField(max_length=100, blank=True, db_index=True)
    entity_id = models.CharField(max_length=100, blank=True, db_index=True)
    payload = models.JSONField(default=dict)
    processed_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["source_module", "event_type", "created_at"])]

    def __str__(self):
        return f"{self.source_module}.{self.event_type}"


class DataSyncLog(UCEModel):
    class ResolutionStrategy(models.TextChoices):
        TIMESTAMP = "timestamp", "Last-Write-Wins"
        PRIORITY = "priority", "Module-Priority"
        MANUAL = "manual", "Manual Review"

    source_module = models.CharField(max_length=50, db_index=True)
    target_module = models.CharField(max_length=50, db_index=True)
    entity_id = models.CharField(max_length=100, db_index=True)
    conflict_detected = models.BooleanField(default=False, db_index=True)
    resolution_strategy = models.CharField(max_length=20, choices=ResolutionStrategy.choices, default=ResolutionStrategy.TIMESTAMP)
    resolved_at = models.DateTimeField(null=True, blank=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["source_module", "target_module", "entity_id"])]

    def __str__(self):
        return f"{self.source_module}->{self.target_module}:{self.entity_id}"

