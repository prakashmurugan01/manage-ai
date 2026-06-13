from django.contrib import admin

from .models import AgentCommand, DeploymentSignal, MachineAgent, ManagedProject, ProjectLogEntry, ProjectWebhookEvent, RuntimeMetric


@admin.register(MachineAgent)
class MachineAgentAdmin(admin.ModelAdmin):
    list_display = ("name", "machine_id", "environment", "status", "hostname", "last_seen_at")
    search_fields = ("name", "machine_id", "hostname", "token_prefix")
    list_filter = ("environment", "status")


@admin.register(ManagedProject)
class ManagedProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "framework", "environment", "runtime_status", "build_status", "deployment_status", "port", "health_score")
    search_fields = ("name", "external_id", "repository_url", "current_branch")
    list_filter = ("environment", "framework", "runtime_status", "build_status", "deployment_status")


admin.site.register(RuntimeMetric)
admin.site.register(ProjectLogEntry)
admin.site.register(DeploymentSignal)
admin.site.register(ProjectWebhookEvent)
admin.site.register(AgentCommand)
