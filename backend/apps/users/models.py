from django.conf import settings
from django.db import models

from apps.core.models import UCEModel


DEFAULT_PERMISSION_MATRIX = {
    "admin": {"*": ["create", "read", "update", "delete", "export"]},
    "manager": {"crm": ["create", "read", "update"], "erp": ["read"], "hr": ["read"], "inventory": ["read", "update"], "projects": ["create", "read", "update"]},
    "analyst": {"crm": ["read", "export"], "erp": ["read", "export"], "hr": ["read"], "inventory": ["read"], "projects": ["read", "export"]},
    "viewer": {"crm": ["read"], "erp": ["read"], "hr": ["read"], "inventory": ["read"], "projects": ["read"]},
}


class Role(UCEModel):
    class BuiltInRole(models.TextChoices):
        ADMIN = "admin", "Admin"
        MANAGER = "manager", "Manager"
        ANALYST = "analyst", "Analyst"
        VIEWER = "viewer", "Viewer"

    name = models.CharField(max_length=40, choices=BuiltInRole.choices, unique=True)
    display_name = models.CharField(max_length=80)
    permissions = models.JSONField(default=dict)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.permissions:
            self.permissions = DEFAULT_PERMISSION_MATRIX.get(self.name, {})
        super().save(*args, **kwargs)

    def __str__(self):
        return self.display_name


class UserRoleAssignment(UCEModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="uce_role_assignments", on_delete=models.CASCADE, db_index=True)
    role = models.ForeignKey("uce_users.Role", related_name="assignments", on_delete=models.CASCADE, db_index=True)
    module_scope = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["user_id", "role_id"]
        constraints = [models.UniqueConstraint(fields=["user", "role"], name="unique_uce_user_role")]

    def __str__(self):
        return f"{self.user} {self.role}"

