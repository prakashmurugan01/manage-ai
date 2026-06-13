from django.conf import settings
from django.db import models

from apps.core.models import UCEModel


class Company(UCEModel):
    name = models.CharField(max_length=180, db_index=True)
    industry = models.CharField(max_length=120, blank=True, db_index=True)
    size = models.CharField(max_length=80, blank=True)
    annual_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0, db_index=True)
    status = models.CharField(max_length=50, default="active", db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["name", "status"])]

    def __str__(self):
        return self.name


class Contact(UCEModel):
    name = models.CharField(max_length=180, db_index=True)
    email = models.EmailField(db_index=True)
    phone = models.CharField(max_length=40, blank=True)
    company = models.ForeignKey("crm.Company", related_name="contacts", on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    lifecycle_stage = models.CharField(max_length=60, default="lead", db_index=True)
    last_activity = models.DateTimeField(null=True, blank=True, db_index=True)
    total_spend = models.DecimalField(max_digits=14, decimal_places=2, default=0, db_index=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="crm_contacts", on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    tags = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["company", "lifecycle_stage"])]

    def __str__(self):
        return self.name


class Deal(UCEModel):
    title = models.CharField(max_length=180, db_index=True)
    company = models.ForeignKey("crm.Company", related_name="deals", on_delete=models.CASCADE, db_index=True)
    value = models.DecimalField(max_digits=14, decimal_places=2, default=0, db_index=True)
    stage = models.CharField(max_length=60, default="qualified", db_index=True)
    probability = models.PositiveSmallIntegerField(default=0)
    expected_close = models.DateField(null=True, blank=True, db_index=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="crm_deals", on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    linked_project = models.ForeignKey("projects.UCEProject", related_name="deals", on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["stage", "expected_close"])]

    def __str__(self):
        return self.title


class Activity(UCEModel):
    class ActivityType(models.TextChoices):
        CALL = "call", "Call"
        EMAIL = "email", "Email"
        MEETING = "meeting", "Meeting"

    type = models.CharField(max_length=20, choices=ActivityType.choices, db_index=True)
    contact = models.ForeignKey("crm.Contact", related_name="activities", on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    deal = models.ForeignKey("crm.Deal", related_name="activities", on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    notes = models.TextField(blank=True)
    outcome = models.CharField(max_length=160, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="crm_activities", on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    activity_date = models.DateTimeField(db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-activity_date"]
        indexes = [models.Index(fields=["type", "activity_date"])]

    def __str__(self):
        return f"{self.type} {self.activity_date:%Y-%m-%d}"

