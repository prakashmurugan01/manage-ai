from django.contrib import admin

from .models import Task, TaskComment


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "status", "priority", "assignee", "due_date", "updated_at")
    list_filter = ("status", "priority", "ai_suggested")
    search_fields = ("title", "description", "project__name")


@admin.register(TaskComment)
class TaskCommentAdmin(admin.ModelAdmin):
    list_display = ("task", "author", "is_internal", "created_at")
    search_fields = ("body", "task__title", "author__email")
