import uuid

from django.contrib.auth.models import AbstractUser, UserManager as DjangoUserManager
from django.db import models


class UserManager(DjangoUserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", User.Role.SUPER_ADMIN)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return super().create_superuser(username, email=email, password=password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        SUPER_ADMIN = "SUPER_ADMIN", "Super Admin"
        ADMIN = "ADMIN", "Admin"
        DEVELOPER = "DEVELOPER", "Developer"
        CLIENT = "CLIENT", "Client"

    class ApprovalStatus(models.TextChoices):
        PENDING = "PENDING", "Pending Approval"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        SUSPENDED = "SUSPENDED", "Suspended"

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.CLIENT)
    approval_status = models.CharField(max_length=32, choices=ApprovalStatus.choices, default=ApprovalStatus.APPROVED, db_index=True)
    rejection_reason = models.TextField(blank=True)
    approved_by = models.ForeignKey("self", related_name="approved_users", on_delete=models.SET_NULL, blank=True, null=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    suspended_at = models.DateTimeField(blank=True, null=True)
    department = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    secret_id = models.CharField(max_length=32, unique=True, blank=True, null=True, db_index=True)
    role_title = models.CharField(max_length=140, blank=True)
    skills = models.JSONField(default=list, blank=True)
    bio = models.TextField(blank=True)
    availability_status = models.CharField(max_length=80, blank=True, default="Available")
    last_seen_at = models.DateTimeField(blank=True, null=True)
    company = models.ForeignKey("enterprise.Company", related_name="users", on_delete=models.SET_NULL, blank=True, null=True)
    face_login_enabled = models.BooleanField(default=False)
    face_image = models.ImageField(upload_to="face_profiles/", blank=True, null=True)
    face_hash = models.CharField(max_length=256, blank=True)
    face_embeddings = models.JSONField(default=list, blank=True)
    face_security_checks = models.JSONField(default=dict, blank=True)
    face_enrolled_at = models.DateTimeField(blank=True, null=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        ordering = ["first_name", "last_name", "email"]

    def __str__(self):
        return self.get_full_name() or self.email

    def save(self, *args, **kwargs):
        if not self.secret_id:
            self.secret_id = self._generate_secret_id()
            if kwargs.get("update_fields"):
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {"secret_id"}
        super().save(*args, **kwargs)

    def _generate_secret_id(self):
        prefix = "DEV" if self.role == self.Role.DEVELOPER else "USR"
        while True:
            value = f"{prefix}-{uuid.uuid4().hex[:8].upper()}"
            if not self.__class__.objects.filter(secret_id=value).exists():
                return value


class Team(models.Model):
    company = models.ForeignKey("enterprise.Company", related_name="teams", on_delete=models.SET_NULL, blank=True, null=True)
    name = models.CharField(max_length=160, unique=True)
    description = models.TextField(blank=True)
    lead = models.ForeignKey(User, related_name="led_teams", on_delete=models.SET_NULL, blank=True, null=True)
    members = models.ManyToManyField(User, related_name="teams", blank=True)
    max_members = models.PositiveSmallIntegerField(default=50)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, related_name="created_teams", on_delete=models.SET_NULL, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["name", "is_active"])]

    def __str__(self):
        return self.name
