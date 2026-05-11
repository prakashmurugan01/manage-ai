from django.contrib import admin

from .models import Project, ProjectCommit


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "priority", "connection_type", "connection_status", "owner", "client", "progress", "health_score", "updated_at")
    list_filter = ("status", "priority", "connection_type", "connection_status")
    search_fields = ("name", "slug", "description", "project_idea", "repository_url", "github_owner", "github_repo")
    filter_horizontal = ("admins", "developers")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("flow_generated_at",)


@admin.register(ProjectCommit)
class ProjectCommitAdmin(admin.ModelAdmin):
    list_display = ("project", "branch", "sha", "author_login", "author_email", "committed_at")
    list_filter = ("branch",)
    search_fields = ("project__name", "sha", "message", "author_login", "author_email")
