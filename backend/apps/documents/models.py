from pathlib import Path

from django.conf import settings
from django.db import models

from apps.projects.models import Project, TimeStampedModel


def document_upload_path(instance, filename):
    return f"projects/{instance.project_id}/documents/{filename}"


class Document(TimeStampedModel):
    class Visibility(models.TextChoices):
        INTERNAL = "INTERNAL", "Internal"
        CLIENT = "CLIENT", "Client"
        PUBLIC = "PUBLIC", "Public"

    class ReviewStatus(models.TextChoices):
        PENDING = "PENDING", "Pending review"
        APPROVED = "APPROVED", "Approved"
        CORRECTION_REQUESTED = "CORRECTION_REQUESTED", "Correction requested"
        REJECTED = "REJECTED", "Rejected"

    project = models.ForeignKey(Project, related_name="documents", on_delete=models.CASCADE)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="uploaded_documents", on_delete=models.SET_NULL, blank=True, null=True)
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to=document_upload_path)
    category = models.CharField(max_length=80, default="General")
    visibility = models.CharField(max_length=32, choices=Visibility.choices, default=Visibility.INTERNAL)
    version = models.CharField(max_length=30, default="1.0")
    file_size = models.PositiveBigIntegerField(default=0)
    extension = models.CharField(max_length=20, blank=True)
    review_status = models.CharField(max_length=32, choices=ReviewStatus.choices, default=ReviewStatus.PENDING)
    review_note = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="reviewed_documents", on_delete=models.SET_NULL, blank=True, null=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["project", "visibility"])]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.file:
            self.file_size = getattr(self.file, "size", 0) or self.file_size
            self.extension = Path(self.file.name).suffix.lower().replace(".", "")[:20]
        super().save(*args, **kwargs)
