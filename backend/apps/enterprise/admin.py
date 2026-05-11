from django.contrib import admin

from .models import (
    APIKey,
    APIKeyGrant,
    Company,
    CompanyService,
    CollaborationChannel,
    CollaborationMessage,
    ConnectionEvent,
    EmailEvent,
    FeatureFlag,
    HostingConnection,
    NetworkTelemetry,
    ProjectEstimate,
    ServerControlState,
    UniversalConnector,
    VoiceCommandIntent,
)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "created_at")
    search_fields = ("name", "slug", "domain")


admin.site.register(CompanyService)
admin.site.register(CollaborationChannel)
admin.site.register(CollaborationMessage)
admin.site.register(UniversalConnector)
admin.site.register(ConnectionEvent)
admin.site.register(FeatureFlag)
admin.site.register(APIKey)
admin.site.register(APIKeyGrant)
admin.site.register(ProjectEstimate)
admin.site.register(EmailEvent)
admin.site.register(HostingConnection)
admin.site.register(ServerControlState)
admin.site.register(NetworkTelemetry)
admin.site.register(VoiceCommandIntent)
