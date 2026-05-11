from django.contrib import admin

from .models import TaskSuggestion


@admin.register(TaskSuggestion)
class TaskSuggestionAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "priority", "confidence", "status", "created_at")
    list_filter = ("status", "priority")
    search_fields = ("title", "description", "rationale", "project__name")
