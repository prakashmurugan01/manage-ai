from django.contrib import admin

from .models import DeploymentControl, DeploymentHistory


@admin.register(DeploymentControl)
class DeploymentControlAdmin(admin.ModelAdmin):
    list_display = ("project", "environment", "is_enabled", "status", "version", "last_deployed_at")
    list_filter = ("environment", "is_enabled", "status")
    search_fields = ("project__name", "version")


@admin.register(DeploymentHistory)
class DeploymentHistoryAdmin(admin.ModelAdmin):
    list_display = ("deployment", "is_enabled", "status", "version", "actor", "created_at")
    list_filter = ("is_enabled", "status")
