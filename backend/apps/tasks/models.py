from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.projects.models import Project, TimeStampedModel


class Task(TimeStampedModel):
    class Status(models.TextChoices):
        BACKLOG = "BACKLOG", "Backlog"
        TODO = "TODO", "To do"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        REVIEW = "REVIEW", "Review"
        DONE = "DONE", "Done"
        BLOCKED = "BLOCKED", "Blocked"

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        CRITICAL = "CRITICAL", "Critical"

    class ApprovalStatus(models.TextChoices):
        NOT_SUBMITTED = "NOT_SUBMITTED", "Not submitted"
        PENDING = "PENDING", "Pending approval"
        APPROVED = "APPROVED", "Approved"
        DISAPPROVED = "DISAPPROVED", "Disapproved"

    project = models.ForeignKey(Project, related_name="tasks", on_delete=models.CASCADE)
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.BACKLOG)
    priority = models.CharField(max_length=32, choices=Priority.choices, default=Priority.MEDIUM)
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="assigned_tasks", on_delete=models.SET_NULL, blank=True, null=True)
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="reported_tasks", on_delete=models.SET_NULL, blank=True, null=True)
    due_date = models.DateField(blank=True, null=True)
    estimated_hours = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    logged_hours = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    story_points = models.PositiveSmallIntegerField(default=0)
    workflow_day = models.PositiveSmallIntegerField(default=1)
    progress_percent = models.PositiveSmallIntegerField(default=0)
    day_progress = models.JSONField(default=dict, blank=True)
    delay_reason = models.TextField(blank=True)
    completion_note = models.TextField(blank=True)
    approval_status = models.CharField(max_length=32, choices=ApprovalStatus.choices, default=ApprovalStatus.NOT_SUBMITTED)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="approved_tasks", on_delete=models.SET_NULL, blank=True, null=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    review_note = models.TextField(blank=True)
    depends_on = models.ManyToManyField("self", symmetrical=False, related_name="unlocks", blank=True)
    workflow_loop_key = models.CharField(max_length=80, blank=True)
    ai_suggested = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "-updated_at"]
        indexes = [
            models.Index(fields=["project", "status", "position"]),
            models.Index(fields=["assignee", "status"]),
            models.Index(fields=["priority"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.progress_percent = max(0, min(100, int(self.progress_percent or 0)))
        if self.status == self.Status.DONE:
            self.progress_percent = 100
            if kwargs.get("update_fields"):
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {"progress_percent"}
        if self.status == self.Status.DONE and not self.completed_at:
            self.completed_at = timezone.now()
            if kwargs.get("update_fields"):
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {"completed_at"}
        if self.status != self.Status.DONE:
            self.completed_at = None
            if kwargs.get("update_fields"):
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {"completed_at"}
        super().save(*args, **kwargs)
        if self.project_id:
            self.project.recalculate_progress()


class TaskComment(TimeStampedModel):
    task = models.ForeignKey(Task, related_name="comments", on_delete=models.CASCADE)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="task_comments", on_delete=models.CASCADE)
    body = models.TextField()
    is_internal = models.BooleanField(default=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment on {self.task_id} by {self.author_id}"
