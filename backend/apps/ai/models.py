from django.conf import settings
from django.db import models

from apps.projects.models import Project, TimeStampedModel


def assistant_attachment_path(instance, filename):
    session_id = instance.message.session_id if instance.message_id else "unassigned"
    return f"assistant/{session_id}/{filename}"


class TaskSuggestion(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        APPROVED = "APPROVED", "Approved"
        DISMISSED = "DISMISSED", "Dismissed"

    project = models.ForeignKey(Project, related_name="task_suggestions", on_delete=models.CASCADE)
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    priority = models.CharField(max_length=32, default="MEDIUM")
    story_points = models.PositiveSmallIntegerField(default=3)
    confidence = models.DecimalField(max_digits=4, decimal_places=2, default=0.75)
    rationale = models.TextField(blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="task_suggestions", on_delete=models.SET_NULL, blank=True, null=True)

    class Meta:
        ordering = ["-confidence", "-created_at"]

    def __str__(self):
        return self.title


class AssistantSession(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        ARCHIVED = "ARCHIVED", "Archived"

    class Mode(models.TextChoices):
        GENERAL = "GENERAL", "General"
        HOSTING = "HOSTING", "Hosting Manager"
        DEVOPS = "DEVOPS", "DevOps"
        PROJECT = "PROJECT", "Project Assistant"
        SUPPORT = "SUPPORT", "Support"
        FILES = "FILES", "File Analyzer"
        AUTOMATION = "AUTOMATION", "Automation"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="assistant_sessions", on_delete=models.CASCADE)
    project = models.ForeignKey(Project, related_name="assistant_sessions", on_delete=models.SET_NULL, blank=True, null=True)
    title = models.CharField(max_length=180, default="AI Command Session")
    mode = models.CharField(max_length=24, choices=Mode.choices, default=Mode.GENERAL)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    model_provider = models.CharField(max_length=40, default="local")
    model_name = models.CharField(max_length=80, default="manageai-enterprise-local")
    memory = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["owner", "status", "-updated_at"])]

    def __str__(self):
        return self.title


class AssistantMessage(TimeStampedModel):
    class Role(models.TextChoices):
        USER = "USER", "User"
        ASSISTANT = "ASSISTANT", "Assistant"
        SYSTEM = "SYSTEM", "System"

    session = models.ForeignKey(AssistantSession, related_name="messages", on_delete=models.CASCADE)
    role = models.CharField(max_length=16, choices=Role.choices)
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["session", "created_at"])]

    def __str__(self):
        return f"{self.session_id} {self.role}"


class AssistantAttachment(TimeStampedModel):
    message = models.ForeignKey(AssistantMessage, related_name="attachments", on_delete=models.CASCADE)
    file = models.FileField(upload_to=assistant_attachment_path)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=160, blank=True)
    size_bytes = models.PositiveBigIntegerField(default=0)
    analysis = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["created_at"]

    def save(self, *args, **kwargs):
        if self.file:
            self.size_bytes = getattr(self.file, "size", 0) or self.size_bytes
        super().save(*args, **kwargs)

    def __str__(self):
        return self.original_name
