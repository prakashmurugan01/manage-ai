from django.conf import settings
from django.db import models

from apps.projects.models import Project, TimeStampedModel
from apps.tasks.models import Task


class Notification(TimeStampedModel):
    class Type(models.TextChoices):
        EXPIRY_WARNING = "expiry_warning", "Expiry warning"
        SERVER_ALERT = "server_alert", "Server alert"
        DISK_ALERT = "disk_alert", "Disk alert"
        API_ABUSE = "api_abuse", "API abuse"
        MAINTENANCE = "maintenance", "Maintenance"
        MANUAL = "manual", "Manual"
        INFO = "INFO", "Info"
        TASK = "TASK", "Task"
        DEPLOYMENT = "DEPLOYMENT", "Deployment"
        FILE = "FILE", "File"
        ALERT = "ALERT", "Alert"
        WARNING = "WARNING", "Warning"
        SUCCESS = "SUCCESS", "Success"

    class Urgency(models.TextChoices):
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        CRITICAL = "critical", "Critical"

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="notifications", on_delete=models.CASCADE)
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="sent_notifications", on_delete=models.SET_NULL, blank=True, null=True)
    title = models.CharField(max_length=200)
    message = models.TextField()
    type = models.CharField(max_length=32, choices=Type.choices, default=Type.INFO)
    urgency = models.CharField(max_length=16, choices=Urgency.choices, default=Urgency.INFO, db_index=True)
    is_read = models.BooleanField(default=False)
    is_sent_email = models.BooleanField(default=False)
    project = models.ForeignKey(Project, related_name="notifications", on_delete=models.CASCADE, blank=True, null=True)
    task = models.ForeignKey(Task, related_name="notifications", on_delete=models.CASCADE, blank=True, null=True)
    hosted_project = models.ForeignKey("hosting.HostedProject", related_name="notifications", on_delete=models.CASCADE, blank=True, null=True)
    server = models.ForeignKey("server_monitor.Server", related_name="notifications", on_delete=models.CASCADE, blank=True, null=True)
    days_threshold = models.IntegerField(null=True, blank=True)

    @property
    def user(self):
        return self.recipient

    @user.setter
    def user(self, value):
        self.recipient = value

    @property
    def notification_type(self):
        return self.type

    @notification_type.setter
    def notification_type(self, value):
        self.type = value

    @property
    def related_project(self):
        return self.hosted_project

    @related_project.setter
    def related_project(self, value):
        self.hosted_project = value

    @property
    def related_server(self):
        return self.server

    @related_server.setter
    def related_server(self, value):
        self.server = value

    @property
    def is_emailed(self):
        return self.is_sent_email

    @is_emailed.setter
    def is_emailed(self, value):
        self.is_sent_email = value

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read"]),
            models.Index(fields=["type", "urgency", "-created_at"]),
            models.Index(fields=["hosted_project", "days_threshold", "-created_at"]),
        ]

    def __str__(self):
        return self.title
