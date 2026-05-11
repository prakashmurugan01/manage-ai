from django.conf import settings
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Project(TimeStampedModel):
    class Status(models.TextChoices):
        PLANNING = "PLANNING", "Planning"
        ACTIVE = "ACTIVE", "Active"
        ON_HOLD = "ON_HOLD", "On hold"
        COMPLETED = "COMPLETED", "Completed"
        ARCHIVED = "ARCHIVED", "Archived"

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        CRITICAL = "CRITICAL", "Critical"

    class ConnectionType(models.TextChoices):
        NONE = "NONE", "None"
        LOCAL = "LOCAL", "Local"
        HOSTED = "HOSTED", "Hosted"
        GITHUB = "GITHUB", "GitHub"

    class ConnectionStatus(models.TextChoices):
        DISCONNECTED = "DISCONNECTED", "Disconnected"
        CONNECTED = "CONNECTED", "Connected"
        SYNCING = "SYNCING", "Syncing"
        DEPLOYING = "DEPLOYING", "Deploying"
        ERROR = "ERROR", "Error"

    class ApprovalStatus(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        IN_REVIEW = "IN_REVIEW", "In review"
        APPROVED = "APPROVED", "Approved"
        CORRECTION_REQUESTED = "CORRECTION_REQUESTED", "Correction requested"

    name = models.CharField(max_length=180)
    company = models.ForeignKey("enterprise.Company", related_name="projects", on_delete=models.SET_NULL, blank=True, null=True)
    slug = models.SlugField(max_length=200, unique=True)
    project_idea = models.TextField(blank=True)
    description = models.TextField(blank=True)
    technologies_used = models.JSONField(default=list, blank=True)
    features_to_implement = models.JSONField(default=list, blank=True)
    project_flow = models.JSONField(default=list, blank=True)
    flow_generated_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PLANNING)
    priority = models.CharField(max_length=32, choices=Priority.choices, default=Priority.MEDIUM)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="owned_projects", on_delete=models.PROTECT)
    client = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="client_projects", on_delete=models.PROTECT, blank=True, null=True)
    admins = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="admin_projects", blank=True)
    developers = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="developer_projects", blank=True)
    teams = models.ManyToManyField("accounts.Team", related_name="projects", blank=True)
    start_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField(blank=True, null=True)
    workflow_days = models.PositiveSmallIntegerField(default=7)
    progress = models.PositiveSmallIntegerField(default=0)
    approval_status = models.CharField(max_length=32, choices=ApprovalStatus.choices, default=ApprovalStatus.DRAFT)
    approval_note = models.TextField(blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="approved_projects", on_delete=models.SET_NULL, blank=True, null=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    budget = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    health_score = models.PositiveSmallIntegerField(default=100)
    repository_url = models.URLField(blank=True)
    local_repository_path = models.CharField(max_length=500, blank=True)
    connection_type = models.CharField(max_length=24, choices=ConnectionType.choices, default=ConnectionType.NONE)
    connection_status = models.CharField(max_length=24, choices=ConnectionStatus.choices, default=ConnectionStatus.DISCONNECTED)
    connection_status_message = models.TextField(blank=True)
    local_url = models.URLField(blank=True)
    hosted_url = models.URLField(blank=True)
    github_owner = models.CharField(max_length=120, blank=True)
    github_repo = models.CharField(max_length=160, blank=True)
    github_default_branch = models.CharField(max_length=120, blank=True, default="main")
    selected_branch = models.CharField(max_length=120, blank=True)
    last_synced_at = models.DateTimeField(blank=True, null=True)
    last_commit_sha = models.CharField(max_length=80, blank=True)
    last_commit_message = models.CharField(max_length=280, blank=True)
    last_commit_author = models.CharField(max_length=180, blank=True)
    last_commit_at = models.DateTimeField(blank=True, null=True)
    tags = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="created_projects", on_delete=models.SET_NULL, blank=True, null=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["status", "priority"]),
            models.Index(fields=["slug"]),
        ]

    def __str__(self):
        return self.name

    def recalculate_progress(self):
        tasks = self.tasks.all()
        total = tasks.count()
        if not total:
            self.progress = 0
        else:
            self.progress = round(sum(task.progress_percent for task in tasks) / total)
        self.health_score = max(0, min(100, 100 - tasks.filter(status="BLOCKED").count() * 15))
        self.save(update_fields=["progress", "health_score", "updated_at"])


class ProjectCommit(TimeStampedModel):
    project = models.ForeignKey(Project, related_name="commits", on_delete=models.CASCADE)
    sha = models.CharField(max_length=80)
    branch = models.CharField(max_length=120, blank=True)
    message = models.CharField(max_length=500, blank=True)
    author_name = models.CharField(max_length=180, blank=True)
    author_email = models.EmailField(blank=True)
    author_login = models.CharField(max_length=120, blank=True)
    committed_at = models.DateTimeField(blank=True, null=True)
    html_url = models.URLField(blank=True)

    class Meta:
        ordering = ["-committed_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["project", "sha", "branch"], name="unique_project_commit_branch"),
        ]
        indexes = [
            models.Index(fields=["project", "branch", "committed_at"]),
            models.Index(fields=["author_email"]),
        ]

    def __str__(self):
        short_sha = self.sha[:7] if self.sha else "commit"
        return f"{self.project.name} {short_sha}"
