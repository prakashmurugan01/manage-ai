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


class DesktopDevice(UCEModel):
    class DeviceType(models.TextChoices):
        DESKTOP = "desktop", "Desktop"
        LAPTOP = "laptop", "Laptop"
        MOBILE = "mobile", "Mobile"
        TABLET = "tablet", "Tablet"
        SERVER = "server", "Server"
        NAS = "nas", "NAS"
        STORAGE = "storage", "Storage"

    class Status(models.TextChoices):
        ONLINE = "online", "Online"
        OFFLINE = "offline", "Offline"
        MAINTENANCE = "maintenance", "Maintenance"

    device_id = models.CharField(max_length=80, unique=True, db_index=True)
    name = models.CharField(max_length=160, db_index=True)
    device_type = models.CharField(max_length=30, choices=DeviceType.choices, default=DeviceType.DESKTOP, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    mac_address = models.CharField(max_length=64, blank=True, db_index=True)
    os_name = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OFFLINE, db_index=True)
    storage_path = models.CharField(max_length=1000)
    total_storage_bytes = models.BigIntegerField(default=0)
    used_storage_bytes = models.BigIntegerField(default=0)
    cpu_percent = models.FloatField(default=0)
    ram_percent = models.FloatField(default=0)
    disk_percent = models.FloatField(default=0)
    transfer_status = models.CharField(max_length=120, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True, db_index=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="desktop_devices", on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["status", "device_type"]),
            models.Index(fields=["owner", "status"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.device_id})"


class DeviceConnection(UCEModel):
    class Status(models.TextChoices):
        CONNECTED = "connected", "Connected"
        DISCONNECTED = "disconnected", "Disconnected"
        CONNECTING = "connecting", "Connecting"
        FAILED = "failed", "Failed"

    source_device = models.ForeignKey("file_tracking.DesktopDevice", related_name="outgoing_connections", on_delete=models.CASCADE)
    destination_device = models.ForeignKey("file_tracking.DesktopDevice", related_name="incoming_connections", on_delete=models.CASCADE)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DISCONNECTED, db_index=True)
    transport = models.CharField(max_length=80, default="websocket", db_index=True)
    encryption = models.CharField(max_length=80, default="TLS 1.3")
    connected_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="device_connections", on_delete=models.SET_NULL, null=True, blank=True)
    connected_at = models.DateTimeField(null=True, blank=True, db_index=True)
    disconnected_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["source_device", "destination_device", "status"]),
            models.Index(fields=["status", "updated_at"]),
        ]

    def __str__(self):
        return f"{self.source_device} -> {self.destination_device}: {self.status}"


class ProjectFile(UCEModel):
    class Status(models.TextChoices):
        UPLOADING = "uploading", "Uploading"
        PENDING = "pending", "Pending Review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        DEPLOYING = "deploying", "Deploying"
        DEPLOYED = "deployed", "Deployed"
        FAILED = "failed", "Failed"

    original_name = models.CharField(max_length=255, db_index=True)
    stored_name = models.CharField(max_length=255)
    relative_path = models.CharField(max_length=1000, blank=True)
    storage_path = models.CharField(max_length=1000)
    content_type = models.CharField(max_length=160, blank=True)
    extension = models.CharField(max_length=40, blank=True, db_index=True)
    size_bytes = models.BigIntegerField(default=0, db_index=True)
    checksum = models.CharField(max_length=128, blank=True, db_index=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.PENDING, db_index=True)
    source_device = models.ForeignKey("file_tracking.DesktopDevice", related_name="uploaded_project_files", on_delete=models.SET_NULL, null=True, blank=True)
    destination_device = models.ForeignKey("file_tracking.DesktopDevice", related_name="target_project_files", on_delete=models.SET_NULL, null=True, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="uploaded_project_files", on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="approved_project_files", on_delete=models.SET_NULL, null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="rejected_project_files", on_delete=models.SET_NULL, null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    deployed_at = models.DateTimeField(null=True, blank=True)
    deployed_path = models.CharField(max_length=1000, blank=True)
    security_scan_status = models.CharField(max_length=80, default="clean", db_index=True)
    risk_score = models.PositiveSmallIntegerField(default=0, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["uploaded_by", "status"]),
            models.Index(fields=["destination_device", "status"]),
        ]

    def __str__(self):
        return f"{self.original_name} ({self.status})"


class ChunkUploadSession(UCEModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    upload_id = models.CharField(max_length=120, unique=True, db_index=True)
    file_name = models.CharField(max_length=255)
    relative_path = models.CharField(max_length=1000, blank=True)
    total_size = models.BigIntegerField(default=0)
    total_chunks = models.PositiveIntegerField(default=1)
    received_chunks = models.JSONField(default=list, blank=True)
    temp_dir = models.CharField(max_length=1000)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    source_device = models.ForeignKey("file_tracking.DesktopDevice", related_name="upload_sessions", on_delete=models.SET_NULL, null=True, blank=True)
    destination_device = models.ForeignKey("file_tracking.DesktopDevice", related_name="incoming_upload_sessions", on_delete=models.SET_NULL, null=True, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="chunk_upload_sessions", on_delete=models.CASCADE)
    project_file = models.ForeignKey("file_tracking.ProjectFile", related_name="upload_sessions", on_delete=models.SET_NULL, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["uploaded_by", "status"])]

    def __str__(self):
        return f"{self.file_name}: {len(self.received_chunks)}/{self.total_chunks}"


class DesktopTransferJob(UCEModel):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    source_device = models.ForeignKey("file_tracking.DesktopDevice", related_name="desktop_transfer_sources", on_delete=models.SET_NULL, null=True, blank=True)
    destination_device = models.ForeignKey("file_tracking.DesktopDevice", related_name="desktop_transfer_destinations", on_delete=models.SET_NULL, null=True, blank=True)
    project_file = models.ForeignKey("file_tracking.ProjectFile", related_name="transfer_jobs", on_delete=models.SET_NULL, null=True, blank=True)
    file_name = models.CharField(max_length=255, db_index=True)
    source_path = models.CharField(max_length=1000)
    destination_path = models.CharField(max_length=1000)
    size_bytes = models.BigIntegerField(default=0, db_index=True)
    bytes_transferred = models.BigIntegerField(default=0)
    progress_percent = models.FloatField(default=0)
    speed_bytes_per_sec = models.FloatField(default=0)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.QUEUED, db_index=True)
    transfer_mode = models.CharField(max_length=80, default="chunked")
    encryption = models.CharField(max_length=80, default="TLS 1.3")
    checksum = models.CharField(max_length=128, blank=True, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="desktop_transfer_uploads", on_delete=models.SET_NULL, null=True, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="desktop_transfer_approvals", on_delete=models.SET_NULL, null=True, blank=True)
    last_error = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["source_device", "destination_device"]),
            models.Index(fields=["uploaded_by", "status"]),
        ]

    def __str__(self):
        return f"{self.file_name}: {self.status}"


class PhysicalStorageFile(UCEModel):
    device = models.ForeignKey("file_tracking.DesktopDevice", related_name="physical_storage_files", on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=255, db_index=True)
    path = models.CharField(max_length=1000, unique=True)
    extension = models.CharField(max_length=40, blank=True, db_index=True)
    size_bytes = models.BigIntegerField(default=0, db_index=True)
    checksum = models.CharField(max_length=128, blank=True, db_index=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="physical_storage_files", on_delete=models.SET_NULL, null=True, blank=True)
    uploaded_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["device", "extension"])]

    def __str__(self):
        return self.name


class DesktopTransferAuditLog(UCEModel):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="desktop_transfer_audit_logs", on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=80, db_index=True)
    message = models.CharField(max_length=500)
    device = models.ForeignKey("file_tracking.DesktopDevice", related_name="audit_logs", on_delete=models.SET_NULL, null=True, blank=True)
    project_file = models.ForeignKey("file_tracking.ProjectFile", related_name="audit_logs", on_delete=models.SET_NULL, null=True, blank=True)
    transfer_job = models.ForeignKey("file_tracking.DesktopTransferJob", related_name="audit_logs", on_delete=models.SET_NULL, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["action", "created_at"])]

    def __str__(self):
        return f"{self.action}: {self.message}"
