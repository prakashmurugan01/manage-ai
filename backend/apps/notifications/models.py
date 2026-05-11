from django.conf import settings
from django.db import models

from apps.projects.models import Project, TimeStampedModel
from apps.tasks.models import Task


class Notification(TimeStampedModel):
    class Type(models.TextChoices):
        INFO = "INFO", "Info"
        TASK = "TASK", "Task"
        DEPLOYMENT = "DEPLOYMENT", "Deployment"
        FILE = "FILE", "File"
        ALERT = "ALERT", "Alert"
        WARNING = "WARNING", "Warning"
        SUCCESS = "SUCCESS", "Success"

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="notifications", on_delete=models.CASCADE)
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="sent_notifications", on_delete=models.SET_NULL, blank=True, null=True)
    title = models.CharField(max_length=160)
    message = models.TextField()
    type = models.CharField(max_length=32, choices=Type.choices, default=Type.INFO)
    is_read = models.BooleanField(default=False)
    project = models.ForeignKey(Project, related_name="notifications", on_delete=models.CASCADE, blank=True, null=True)
    task = models.ForeignKey(Task, related_name="notifications", on_delete=models.CASCADE, blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "is_read"])]

    def __str__(self):
        return self.title
