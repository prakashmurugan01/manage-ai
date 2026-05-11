from django.contrib import admin

from .models import APIRequestLog, AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "entity_type", "entity_id", "actor", "ip_address", "created_at")
    list_filter = ("action", "entity_type")
    search_fields = ("action", "entity_type", "entity_id", "actor__email")


@admin.register(APIRequestLog)
class APIRequestLogAdmin(admin.ModelAdmin):
    list_display = ("method", "path", "status_code", "duration_ms", "user", "created_at")
    list_filter = ("method", "status_code")
    search_fields = ("path", "user__email")
