from django.conf import settings
from django.db import models

from apps.core.models import UCEModel


class DiskVolume(UCEModel):
    class DiskType(models.TextChoices):
        LOCAL = "local", "Local"
        USB = "usb", "USB"
        NETWORK = "network", "Network"
        CLOUD = "cloud", "Cloud"

    label = models.CharField(max_length=120, db_index=True)
    mount_path = models.CharField(max_length=500, unique=True)
    disk_type = models.CharField(max_length=30, choices=DiskType.choices, default=DiskType.LOCAL, db_index=True)
    total_bytes = models.BigIntegerField(default=0)
    used_bytes = models.BigIntegerField(default=0, db_index=True)
    free_bytes = models.BigIntegerField(default=0, db_index=True)
    last_seen_at = models.DateTimeField(null=True, blank=True, db_index=True)
    is_online = models.BooleanField(default=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["label"]
        indexes = [models.Index(fields=["disk_type", "is_online"])]

    def __str__(self):
        return f"{self.label} ({self.mount_path})"


class TrackingRule(UCEModel):
    class RuleType(models.TextChoices):
        LARGE_TRANSFER = "large_transfer", "Large Transfer"
        SENSITIVE_EXTENSION = "sensitive_extension", "Sensitive Extension"
        OFF_HOURS = "off_hours", "Off Hours"
        DISK_PRESSURE = "disk_pressure", "Disk Pressure"

    name = models.CharField(max_length=160, unique=True)
    rule_type = models.CharField(max_length=40, choices=RuleType.choices, db_index=True)
    threshold_bytes = models.BigIntegerField(default=1024 * 1024 * 1024)
    extensions = models.JSONField(default=list, blank=True)
    severity = models.CharField(max_length=20, default="medium", db_index=True)
    is_enabled = models.BooleanField(default=True, db_index=True)
    config = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class FileTransfer(UCEModel):
    class Status(models.TextChoices):
        DETECTED = "detected", "Detected"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        QUARANTINED = "quarantined", "Quarantined"

    file_name = models.CharField(max_length=255, db_index=True)
    file_extension = models.CharField(max_length=40, blank=True, db_index=True)
    mime_type = models.CharField(max_length=120, blank=True, db_index=True)
    checksum = models.CharField(max_length=128, blank=True, db_index=True)
    size_bytes = models.BigIntegerField(default=0, db_index=True)
    source_volume = models.ForeignKey("file_tracking.DiskVolume", related_name="outgoing_transfers", on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    destination_volume = models.ForeignKey("file_tracking.DiskVolume", related_name="incoming_transfers", on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    source_path = models.CharField(max_length=1000, db_index=True)
    destination_path = models.CharField(max_length=1000, db_index=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DETECTED, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    initiated_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="file_transfers", on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    process_name = models.CharField(max_length=160, blank=True, db_index=True)
    risk_score = models.PositiveSmallIntegerField(default=0, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["source_volume", "destination_volume"]),
            models.Index(fields=["file_extension", "size_bytes"]),
        ]

    def __str__(self):
        return f"{self.file_name}: {self.source_path} -> {self.destination_path}"


class FileEvent(UCEModel):
    class EventType(models.TextChoices):
        CREATED = "created", "Created"
        MOVED = "moved", "Moved"
        COPIED = "copied", "Copied"
        DELETED = "deleted", "Deleted"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    event_type = models.CharField(max_length=40, choices=EventType.choices, db_index=True)
    transfer = models.ForeignKey("file_tracking.FileTransfer", related_name="events", on_delete=models.CASCADE, null=True, blank=True, db_index=True)
    source_path = models.CharField(max_length=1000, blank=True, db_index=True)
    destination_path = models.CharField(max_length=1000, blank=True, db_index=True)
    payload = models.JSONField(default=dict)
    observed_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ["-observed_at"]
        indexes = [models.Index(fields=["event_type", "observed_at"])]

    def __str__(self):
        return f"{self.event_type} {self.observed_at}"


class FileAlert(UCEModel):
    class Severity(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ACKNOWLEDGED = "acknowledged", "Acknowledged"
        RESOLVED = "resolved", "Resolved"

    transfer = models.ForeignKey("file_tracking.FileTransfer", related_name="alerts", on_delete=models.CASCADE, null=True, blank=True, db_index=True)
    rule = models.ForeignKey("file_tracking.TrackingRule", related_name="alerts", on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    severity = models.CharField(max_length=20, choices=Severity.choices, default=Severity.MEDIUM, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN, db_index=True)
    message = models.CharField(max_length=500)
    details = models.JSONField(default=dict, blank=True)
    acknowledged_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="acknowledged_file_alerts", on_delete=models.SET_NULL, null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["severity", "status", "created_at"])]

    def __str__(self):
        return self.message

