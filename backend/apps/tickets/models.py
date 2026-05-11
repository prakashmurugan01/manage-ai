from datetime import timedelta

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from apps.projects.models import Project, TimeStampedModel


def ticket_screenshot_path(instance, filename):
    project_id = instance.project_id or "unassigned"
    return f"tickets/{project_id}/screenshots/{filename}"


def ticket_attachment_path(instance, filename):
    project_id = instance.ticket.project_id if instance.ticket_id else "unassigned"
    return f"tickets/{project_id}/attachments/{filename}"


class ServiceItem(TimeStampedModel):
    organization = models.ForeignKey("enterprise.Company", related_name="service_items", on_delete=models.CASCADE, blank=True, null=True)
    name = models.CharField(max_length=180)
    category = models.CharField(max_length=120, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="owned_service_items", on_delete=models.SET_NULL, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("organization", "name")
        indexes = [models.Index(fields=["organization", "is_active"])]

    def __str__(self):
        return self.name


class Ticket(TimeStampedModel):
    class Type(models.TextChoices):
        INCIDENT = "INCIDENT", "Incident"
        SERVICE_REQUEST = "SERVICE_REQUEST", "Service Request"
        PROBLEM = "PROBLEM", "Problem"
        CHANGE = "CHANGE", "Change"
        TASK = "TASK", "Task"

    class Status(models.TextChoices):
        NEW = "NEW", "New"
        ASSIGNED = "ASSIGNED", "Assigned"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        PENDING = "PENDING", "Pending"
        RESOLVED = "RESOLVED", "Resolved"
        CLOSED = "CLOSED", "Closed"
        OPEN = "OPEN", "Open"
        TRIAGED = "TRIAGED", "Triaged"

    class Priority(models.TextChoices):
        P1 = "P1", "P1 Critical"
        P2 = "P2", "P2 High"
        P3 = "P3", "P3 Medium"
        P4 = "P4", "P4 Low"
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        CRITICAL = "CRITICAL", "Critical"

    class Source(models.TextChoices):
        CLIENT = "CLIENT", "Client"
        DEVELOPER = "DEVELOPER", "Developer"
        ADMIN = "ADMIN", "Admin"
        SYSTEM = "SYSTEM", "System"

    class Level(models.IntegerChoices):
        LOW = 1, "Low"
        MEDIUM = 2, "Medium"
        HIGH = 3, "High"
        CRITICAL = 4, "Critical"

    ticket_id = models.CharField(max_length=32, unique=True, blank=True)
    type = models.CharField(max_length=32, choices=Type.choices, default=Type.INCIDENT)
    project = models.ForeignKey(Project, related_name="tickets", on_delete=models.CASCADE)
    organization = models.ForeignKey("enterprise.Company", related_name="tickets", on_delete=models.CASCADE, blank=True, null=True)
    title = models.CharField(max_length=220)
    description = models.TextField()
    screenshot = models.ImageField(upload_to=ticket_screenshot_path, blank=True, null=True)
    priority = models.CharField(max_length=32, choices=Priority.choices, default=Priority.P3)
    severity = models.PositiveSmallIntegerField(choices=Level.choices, default=Level.MEDIUM)
    impact = models.PositiveSmallIntegerField(choices=Level.choices, default=Level.MEDIUM)
    urgency = models.PositiveSmallIntegerField(choices=Level.choices, default=Level.MEDIUM)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.NEW)
    category = models.CharField(max_length=120, blank=True)
    subcategory = models.CharField(max_length=120, blank=True)
    service_item = models.ForeignKey(ServiceItem, related_name="tickets", on_delete=models.SET_NULL, blank=True, null=True)
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="requested_tickets", on_delete=models.SET_NULL, blank=True, null=True)
    raised_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="raised_tickets", on_delete=models.SET_NULL, blank=True, null=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="assigned_tickets", on_delete=models.SET_NULL, blank=True, null=True)
    assigned_group = models.ForeignKey("accounts.Team", related_name="assigned_tickets", on_delete=models.SET_NULL, blank=True, null=True)
    source = models.CharField(max_length=32, choices=Source.choices, default=Source.CLIENT)
    auto_assigned = models.BooleanField(default=False)
    assignment_reason = models.CharField(max_length=240, blank=True)
    first_response_at = models.DateTimeField(blank=True, null=True)
    resolved_at = models.DateTimeField(blank=True, null=True)
    closed_at = models.DateTimeField(blank=True, null=True)
    sla_due_at = models.DateTimeField(blank=True, null=True)
    sla_breached = models.BooleanField(default=False)
    sla_paused_at = models.DateTimeField(blank=True, null=True)
    sla_pause_reason = models.CharField(max_length=240, blank=True)
    parent_ticket = models.ForeignKey("self", related_name="child_tickets", on_delete=models.SET_NULL, blank=True, null=True)
    related_tickets = models.ManyToManyField("self", blank=True, symmetrical=True)
    tags = models.JSONField(default=list, blank=True)
    custom_fields = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["organization", "status", "priority"]),
            models.Index(fields=["project", "status", "priority"]),
            models.Index(fields=["assigned_to", "status"]),
            models.Index(fields=["requester", "status"]),
            models.Index(fields=["raised_by", "status"]),
            models.Index(fields=["sla_due_at", "sla_breached"]),
            models.Index(fields=["ticket_id"]),
        ]

    def __str__(self):
        return self.ticket_id or self.title

    @property
    def effective_requester(self):
        return self.requester or self.raised_by

    @staticmethod
    def normalize_priority(value):
        return {
            "CRITICAL": "P1",
            "HIGH": "P2",
            "MEDIUM": "P3",
            "LOW": "P4",
        }.get(value, value or "P3")

    def _prefix(self):
        return {
            self.Type.INCIDENT: "INC",
            self.Type.SERVICE_REQUEST: "REQ",
            self.Type.PROBLEM: "PRB",
            self.Type.CHANGE: "CHG",
            self.Type.TASK: "TSK",
        }.get(self.type, "INC")

    def assign_ticket_id(self):
        if self.ticket_id:
            return
        year = timezone.localdate().year
        prefix = self._prefix()
        with transaction.atomic():
            counter, _ = TicketSequence.objects.select_for_update().get_or_create(prefix=prefix, year=year)
            counter.next_number += 1
            counter.save(update_fields=["next_number", "updated_at"])
            self.ticket_id = f"{prefix}-{year}-{counter.next_number:05d}"

    def save(self, *args, **kwargs):
        if not self.organization_id and self.project_id:
            self.organization = self.project.company
        if not self.requester_id and self.raised_by_id:
            self.requester_id = self.raised_by_id
        if not self.raised_by_id and self.requester_id:
            self.raised_by_id = self.requester_id
        if self.priority in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
            self.priority = self.normalize_priority(self.priority)
        if not self.ticket_id:
            self.assign_ticket_id()
        now = timezone.now()
        if self.status in {self.Status.ASSIGNED, self.Status.IN_PROGRESS} and not self.first_response_at:
            self.first_response_at = now
        if self.status in {self.Status.RESOLVED, self.Status.CLOSED} and not self.resolved_at:
            self.resolved_at = now
        if self.status == self.Status.CLOSED and not self.closed_at:
            self.closed_at = now
        if self.status not in {self.Status.RESOLVED, self.Status.CLOSED}:
            self.resolved_at = None
            self.closed_at = None
        super().save(*args, **kwargs)


class TicketSequence(TimeStampedModel):
    prefix = models.CharField(max_length=8)
    year = models.PositiveSmallIntegerField()
    next_number = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("prefix", "year")


class SLAPolicy(TimeStampedModel):
    organization = models.ForeignKey("enterprise.Company", related_name="sla_policies", on_delete=models.CASCADE, blank=True, null=True)
    name = models.CharField(max_length=180)
    priority = models.CharField(max_length=32, choices=Ticket.Priority.choices)
    first_response_time = models.DurationField(default=timedelta(hours=1))
    resolution_time = models.DurationField(default=timedelta(hours=8))
    business_hours_only = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["priority", "name"]
        unique_together = ("organization", "name", "priority")
        indexes = [models.Index(fields=["organization", "priority", "is_active"])]

    def __str__(self):
        return f"{self.name} - {self.priority}"


class BusinessHours(TimeStampedModel):
    organization = models.ForeignKey("enterprise.Company", related_name="business_hours", on_delete=models.CASCADE, blank=True, null=True)
    day_of_week = models.PositiveSmallIntegerField(help_text="0=Monday, 6=Sunday")
    start_time = models.TimeField()
    end_time = models.TimeField()
    timezone = models.CharField(max_length=80, default="UTC")

    class Meta:
        ordering = ["day_of_week", "start_time"]
        unique_together = ("organization", "day_of_week", "start_time", "end_time")


class Holiday(TimeStampedModel):
    organization = models.ForeignKey("enterprise.Company", related_name="holidays", on_delete=models.CASCADE, blank=True, null=True)
    name = models.CharField(max_length=160)
    date = models.DateField()

    class Meta:
        ordering = ["date"]
        unique_together = ("organization", "date", "name")


class WorkflowTemplate(TimeStampedModel):
    class TriggerType(models.TextChoices):
        TICKET_CREATED = "TICKET_CREATED", "Ticket Created"
        STATUS_CHANGED = "STATUS_CHANGED", "Status Changed"
        SLA_BREACHED = "SLA_BREACHED", "SLA Breached"
        MANUAL = "MANUAL", "Manual"

    organization = models.ForeignKey("enterprise.Company", related_name="workflow_templates", on_delete=models.CASCADE, blank=True, null=True)
    name = models.CharField(max_length=180)
    trigger_type = models.CharField(max_length=32, choices=TriggerType.choices)
    trigger_conditions = models.JSONField(default=dict, blank=True)
    actions = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["organization", "trigger_type", "is_active"])]

    def __str__(self):
        return self.name


class WorkflowExecution(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        RUNNING = "RUNNING", "Running"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"

    template = models.ForeignKey(WorkflowTemplate, related_name="executions", on_delete=models.CASCADE)
    ticket = models.ForeignKey(Ticket, related_name="workflow_executions", on_delete=models.CASCADE)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    logs = models.JSONField(default=list, blank=True)
    error = models.TextField(blank=True)
    started_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]


class ApprovalTemplate(TimeStampedModel):
    class ApproverType(models.TextChoices):
        USER = "USER", "User"
        ROLE = "ROLE", "Role"
        MANAGER = "MANAGER", "Manager"

    organization = models.ForeignKey("enterprise.Company", related_name="approval_templates", on_delete=models.CASCADE, blank=True, null=True)
    name = models.CharField(max_length=180)
    stages = models.JSONField(default=list, blank=True)
    approver_type = models.CharField(max_length=16, choices=ApproverType.choices, default=ApproverType.USER)
    is_parallel = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ApprovalRequest(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"

    ticket = models.ForeignKey(Ticket, related_name="approval_requests", on_delete=models.CASCADE)
    template = models.ForeignKey(ApprovalTemplate, related_name="requests", on_delete=models.SET_NULL, blank=True, null=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="requested_ticket_approvals", on_delete=models.SET_NULL, blank=True, null=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    current_stage_order = models.PositiveSmallIntegerField(default=1)
    comments = models.TextField(blank=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["ticket", "status"])]

    def refresh_status(self):
        stages = list(self.stages.all())
        if stages and any(stage.status == ApprovalStage.Status.REJECTED for stage in stages):
            self.status = self.Status.REJECTED
            self.completed_at = timezone.now()
        elif stages and all(stage.status == ApprovalStage.Status.APPROVED for stage in stages):
            self.status = self.Status.APPROVED
            self.completed_at = timezone.now()
        self.save(update_fields=["status", "completed_at", "updated_at"])


class ApprovalStage(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        SKIPPED = "SKIPPED", "Skipped"

    approval_request = models.ForeignKey(ApprovalRequest, related_name="stages", on_delete=models.CASCADE)
    order = models.PositiveSmallIntegerField(default=1)
    name = models.CharField(max_length=160)
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="ticket_approval_stages", on_delete=models.SET_NULL, blank=True, null=True)
    approver_role = models.CharField(max_length=32, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    comments = models.TextField(blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="decided_ticket_approvals", on_delete=models.SET_NULL, blank=True, null=True)
    decided_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["approval_request", "order"]
        unique_together = ("approval_request", "order", "name")

    def can_decide(self, user):
        if self.approver_id and self.approver_id == user.id:
            return True
        return bool(self.approver_role and getattr(user, "role", "") == self.approver_role)


class TicketComment(TimeStampedModel):
    ticket = models.ForeignKey(Ticket, related_name="comments", on_delete=models.CASCADE)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="ticket_comments", on_delete=models.CASCADE)
    body = models.TextField()
    is_internal = models.BooleanField(default=False)
    mentions = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="mentioned_ticket_comments", blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Ticket comment {self.ticket_id} by {self.author_id}"


class TicketAttachment(TimeStampedModel):
    ticket = models.ForeignKey(Ticket, related_name="attachments", on_delete=models.CASCADE)
    comment = models.ForeignKey(TicketComment, related_name="attachments", on_delete=models.CASCADE, blank=True, null=True)
    file = models.FileField(upload_to=ticket_attachment_path)
    caption = models.CharField(max_length=160, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="ticket_attachments", on_delete=models.SET_NULL, blank=True, null=True)
    file_size = models.PositiveBigIntegerField(default=0)

    class Meta:
        ordering = ["created_at"]

    def save(self, *args, **kwargs):
        if self.file:
            self.file_size = getattr(self.file, "size", 0) or self.file_size
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Attachment for ticket {self.ticket_id}"


class TicketActivity(models.Model):
    ticket = models.ForeignKey(Ticket, related_name="activities", on_delete=models.CASCADE)
    action = models.CharField(max_length=80)
    field_changed = models.CharField(max_length=80, blank=True)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="ticket_activities", on_delete=models.SET_NULL, blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [models.Index(fields=["ticket", "-timestamp"]), models.Index(fields=["action"])]

    def __str__(self):
        return f"{self.ticket_id} {self.action}"
