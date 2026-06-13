from django.contrib import admin

from .models import AssistantAttachment, AssistantMessage, AssistantSession, TaskSuggestion


@admin.register(TaskSuggestion)
class TaskSuggestionAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "priority", "confidence", "status", "created_at")
    list_filter = ("status", "priority")
    search_fields = ("title", "description", "rationale", "project__name")


class AssistantAttachmentInline(admin.TabularInline):
    model = AssistantAttachment
    extra = 0
    readonly_fields = ("original_name", "content_type", "size_bytes", "analysis", "created_at")


@admin.register(AssistantSession)
class AssistantSessionAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "mode", "status", "model_provider", "model_name", "updated_at")
    list_filter = ("mode", "status", "model_provider")
    search_fields = ("title", "owner__email", "project__name")


@admin.register(AssistantMessage)
class AssistantMessageAdmin(admin.ModelAdmin):
    list_display = ("session", "role", "created_at")
    list_filter = ("role",)
    search_fields = ("content", "session__title", "session__owner__email")
    inlines = [AssistantAttachmentInline]
