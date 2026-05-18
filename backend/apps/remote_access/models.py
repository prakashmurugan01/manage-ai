import secrets
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


def make_token():
    return secrets.token_urlsafe(24)


class RemoteDevice(models.Model):
    class Status(models.TextChoices):
        ONLINE = "ONLINE", "Online"
        OFFLINE = "OFFLINE", "Offline"
        BUSY = "BUSY", "Busy"
        PENDING = "PENDING", "Pending approval"

    name = models.CharField(max_length=160)
    hostname = models.CharField(max_length=160, blank=True)
    platform = models.CharField(max_length=80, blank=True)
    agent_version = models.CharField(max_length=40, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="remote_devices")
    token = models.CharField(max_length=128, unique=True, default=make_token)
    fingerprint = models.CharField(max_length=128, blank=True)
    public_key = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OFFLINE)
    capabilities = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_seen_at", "name"]

    def mark_seen(self, status=Status.ONLINE):
        self.status = status
        self.last_seen_at = timezone.now()
        self.save(update_fields=["status", "last_seen_at", "updated_at"])

    def __str__(self):
        return self.name


class RemoteSession(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "REQUESTED", "Requested"
        APPROVED = "APPROVED", "Approved"
        ACTIVE = "ACTIVE", "Active"
        ENDED = "ENDED", "Ended"
        DENIED = "DENIED", "Denied"
        EXPIRED = "EXPIRED", "Expired"

    class Permission(models.TextChoices):
        VIEW = "VIEW", "View only"
        CONTROL = "CONTROL", "Full control"
        FILES = "FILES", "File access"
        ADMIN = "ADMIN", "Full desktop and disk"

    device = models.ForeignKey(RemoteDevice, on_delete=models.CASCADE, related_name="sessions")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="remote_sessions")
    token = models.CharField(max_length=128, unique=True, default=make_token)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED)
    permission = models.CharField(max_length=20, choices=Permission.choices, default=Permission.VIEW)
    offer = models.JSONField(default=dict, blank=True)
    answer = models.JSONField(default=dict, blank=True)
    ice_candidates = models.JSONField(default=list, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.device} - {self.status}"


class RemoteTransfer(models.Model):
    class Direction(models.TextChoices):
        DOWNLOAD = "DOWNLOAD", "Download"
        UPLOAD = "UPLOAD", "Upload"
        DEVICE_TO_DEVICE = "DEVICE_TO_DEVICE", "Device to device"

    class Status(models.TextChoices):
        QUEUED = "QUEUED", "Queued"
        RUNNING = "RUNNING", "Running"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"
        CANCELED = "CANCELED", "Canceled"

    session = models.ForeignKey(RemoteSession, on_delete=models.CASCADE, related_name="transfers")
    upload_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    direction = models.CharField(max_length=20, choices=Direction.choices)
    source_path = models.TextField()
    target_path = models.TextField(blank=True)
    original_name = models.CharField(max_length=255, blank=True)
    stored_name = models.CharField(max_length=255, blank=True)
    content_type = models.CharField(max_length=160, blank=True)
    size_bytes = models.BigIntegerField(default=0)
    transferred_bytes = models.BigIntegerField(default=0)
    chunk_size = models.PositiveIntegerField(default=1048576)
    total_chunks = models.PositiveIntegerField(default=0)
    completed_chunks = models.JSONField(default=list, blank=True)
    storage_path = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    error = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def completed_chunk_numbers(self):
        return {int(index) for index in self.completed_chunks or []}


class RemoteActivityLog(models.Model):
    class Action(models.TextChoices):
        DEVICE_ONLINE = "DEVICE_ONLINE", "Device online"
        DEVICE_OFFLINE = "DEVICE_OFFLINE", "Device offline"
        SESSION_REQUEST = "SESSION_REQUEST", "Session request"
        SESSION_APPROVED = "SESSION_APPROVED", "Session approved"
        SESSION_DENIED = "SESSION_DENIED", "Session denied"
        SESSION_ENDED = "SESSION_ENDED", "Session ended"
        CONTROL = "CONTROL", "Control input"
        FILE_BROWSE = "FILE_BROWSE", "File browse"
        FILE_DOWNLOAD = "FILE_DOWNLOAD", "File download"
        FILE_UPLOAD = "FILE_UPLOAD", "File upload"
        FILE_DELETE = "FILE_DELETE", "File delete"
        ERROR = "ERROR", "Error"

    device = models.ForeignKey(RemoteDevice, on_delete=models.SET_NULL, null=True, blank=True)
    session = models.ForeignKey(RemoteSession, on_delete=models.SET_NULL, null=True, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=40, choices=Action.choices)
    message = models.CharField(max_length=255)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
