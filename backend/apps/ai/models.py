from django.conf import settings
from django.db import models

from apps.projects.models import Project, TimeStampedModel


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
