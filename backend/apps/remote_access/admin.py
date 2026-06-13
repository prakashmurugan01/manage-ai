from django.contrib import admin

from .models import RemoteActivityLog, RemoteDevice, RemoteSession, RemoteTransfer


@admin.register(RemoteDevice)
class RemoteDeviceAdmin(admin.ModelAdmin):
    list_display = ("name", "hostname", "platform", "status", "owner", "last_seen_at")
    search_fields = ("name", "hostname", "fingerprint", "token")
    list_filter = ("status", "platform")


@admin.register(RemoteSession)
class RemoteSessionAdmin(admin.ModelAdmin):
    list_display = ("device", "requested_by", "permission", "status", "created_at", "started_at", "ended_at")
    list_filter = ("status", "permission")


@admin.register(RemoteTransfer)
class RemoteTransferAdmin(admin.ModelAdmin):
    list_display = ("session", "direction", "status", "source_path", "target_path", "transferred_bytes", "size_bytes")
    list_filter = ("direction", "status")


@admin.register(RemoteActivityLog)
class RemoteActivityLogAdmin(admin.ModelAdmin):
    list_display = ("action", "device", "session", "actor", "created_at")
    list_filter = ("action",)
