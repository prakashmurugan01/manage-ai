from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from apps.accounts.views import AvatarUploadView, CustomTokenObtainPairView, FaceEnrollView, FaceLoginView, MeView, RegisterView, TeamViewSet, UserViewSet
from apps.ai.views import TaskSuggestionViewSet
from apps.audit.views import APIRequestLogViewSet, AuditLogViewSet
from apps.deployments.views import DeploymentControlViewSet
from apps.documents.views import DocumentViewSet
from apps.enterprise.views import (
    APIKeyGrantViewSet,
    APIKeyViewSet,
    AuthenticationSettingsViewSet,
    CloudStorageSettingsViewSet,
    CompanyServiceViewSet,
    CompanyViewSet,
    CollaborationChannelViewSet,
    ConnectionEngineSummaryView,
    ConnectionEventViewSet,
    EmailEventViewSet,
    FeatureFlagViewSet,
    HostingConnectionViewSet,
    ManagementEngineDashboardView,
    NetworkTelemetryViewSet,
    ProjectEstimateViewSet,
    ReportExportView,
    ServerControlViewSet,
    ServerFileAccessViewSet,
    SettingsDashboardView,
    SystemModuleControlViewSet,
    SystemSettingsAuditLogViewSet,
    UniversalConnectorViewSet,
    UserAccessControlViewSet,
    VoiceCommandIntentViewSet,
)
from apps.notifications.views import NotificationViewSet
from apps.projects.views import ProjectViewSet
from apps.remote_access.views import RemoteActivityLogViewSet, RemoteDeviceViewSet, RemoteSessionViewSet, RemoteTransferViewSet
from apps.tasks.views import TaskCommentViewSet, TaskViewSet
from apps.tickets.views import (
    ApprovalRequestViewSet,
    ApprovalStageViewSet,
    ApprovalTemplateViewSet,
    BusinessHoursViewSet,
    HolidayViewSet,
    SLAPolicyViewSet,
    ServiceItemViewSet,
    TicketCommentViewSet,
    TicketViewSet,
    WorkflowExecutionViewSet,
    WorkflowTemplateViewSet,
)

router = DefaultRouter()
router.register("users", UserViewSet, basename="users")
router.register("teams", TeamViewSet, basename="teams")
router.register("projects", ProjectViewSet, basename="projects")
router.register("tasks", TaskViewSet, basename="tasks")
router.register("task-comments", TaskCommentViewSet, basename="task-comments")
router.register("tickets", TicketViewSet, basename="tickets")
router.register("ticket-comments", TicketCommentViewSet, basename="ticket-comments")
router.register("ticket-sla-policies", SLAPolicyViewSet, basename="ticket-sla-policies")
router.register("ticket-business-hours", BusinessHoursViewSet, basename="ticket-business-hours")
router.register("ticket-holidays", HolidayViewSet, basename="ticket-holidays")
router.register("service-items", ServiceItemViewSet, basename="service-items")
router.register("ticket-workflows", WorkflowTemplateViewSet, basename="ticket-workflows")
router.register("ticket-workflow-executions", WorkflowExecutionViewSet, basename="ticket-workflow-executions")
router.register("ticket-approval-templates", ApprovalTemplateViewSet, basename="ticket-approval-templates")
router.register("ticket-approvals", ApprovalRequestViewSet, basename="ticket-approvals")
router.register("ticket-approval-stages", ApprovalStageViewSet, basename="ticket-approval-stages")
router.register("deployments", DeploymentControlViewSet, basename="deployments")
router.register("documents", DocumentViewSet, basename="documents")
router.register("notifications", NotificationViewSet, basename="notifications")
router.register("audit-logs", AuditLogViewSet, basename="audit-logs")
router.register("api-logs", APIRequestLogViewSet, basename="api-logs")
router.register("task-suggestions", TaskSuggestionViewSet, basename="task-suggestions")
router.register("companies", CompanyViewSet, basename="companies")
router.register("company-services", CompanyServiceViewSet, basename="company-services")
router.register("collaboration-channels", CollaborationChannelViewSet, basename="collaboration-channels")
router.register("universal-connectors", UniversalConnectorViewSet, basename="universal-connectors")
router.register("connection-events", ConnectionEventViewSet, basename="connection-events")
router.register("feature-flags", FeatureFlagViewSet, basename="feature-flags")
router.register("api-keys", APIKeyViewSet, basename="api-keys")
router.register("api-key-grants", APIKeyGrantViewSet, basename="api-key-grants")
router.register("project-estimates", ProjectEstimateViewSet, basename="project-estimates")
router.register("email-events", EmailEventViewSet, basename="email-events")
router.register("hosting-connections", HostingConnectionViewSet, basename="hosting-connections")
router.register("server-control", ServerControlViewSet, basename="server-control")
router.register("network-telemetry", NetworkTelemetryViewSet, basename="network-telemetry")
router.register("voice-intents", VoiceCommandIntentViewSet, basename="voice-intents")
router.register("settings/modules", SystemModuleControlViewSet, basename="settings-modules")
router.register("settings/access-controls", UserAccessControlViewSet, basename="settings-access-controls")
router.register("settings/auth", AuthenticationSettingsViewSet, basename="settings-auth")
router.register("settings/storage", CloudStorageSettingsViewSet, basename="settings-storage")
router.register("settings/file-access", ServerFileAccessViewSet, basename="settings-file-access")
router.register("settings/audit-logs", SystemSettingsAuditLogViewSet, basename="settings-audit-logs")
router.register("remote-devices", RemoteDeviceViewSet, basename="remote-devices")
router.register("remote-sessions", RemoteSessionViewSet, basename="remote-sessions")
router.register("remote-transfers", RemoteTransferViewSet, basename="remote-transfers")
router.register("remote-logs", RemoteActivityLogViewSet, basename="remote-logs")


def health_view(request):
    host = request.get_host().split(":")[0]
    port = request.get_port()
    return JsonResponse(
        {
            "status": "ok",
            "message": "ManageAI backend is running. Do not browse to 0.0.0.0; use 127.0.0.1 on this PC or the server LAN IP from another device.",
            "local_url": f"http://127.0.0.1:{port}",
            "lan_url_hint": f"http://{host}:{port}" if host not in {"0.0.0.0", "127.0.0.1", "localhost"} else "http://YOUR_LAN_IP:8001",
            "agent_server_hint": f"ws://{host}:{port}" if host not in {"0.0.0.0", "127.0.0.1", "localhost"} else "ws://YOUR_LAN_IP:8001",
            "api_login": "/api/auth/login/",
        }
    )


urlpatterns = [
    path("", health_view, name="health"),
    path("admin/", admin.site.urls),
    path("api/auth/register/", RegisterView.as_view(), name="register"),
    path("api/auth/login/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/face-login/", FaceLoginView.as_view(), name="face-login"),
    path("api/auth/face-enroll/", FaceEnrollView.as_view(), name="face-enroll"),
    path("api/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("api/auth/me/", MeView.as_view(), name="me"),
    path("api/auth/me/avatar/", AvatarUploadView.as_view(), name="me-avatar"),
    path("api/analytics/", include("apps.analytics.urls")),
    path("api/connection-engine/summary/", ConnectionEngineSummaryView.as_view(), name="connection-engine-summary"),
    path("api/management-engine/dashboard/", ManagementEngineDashboardView.as_view(), name="management-engine-dashboard"),
    path("api/settings/dashboard/", SettingsDashboardView.as_view(), name="settings-dashboard"),
    path("api/reports/<str:kind>/", ReportExportView.as_view(), name="report-export"),
    path("api/", include(router.urls)),
    path("api/v1/", include("apps.core.urls")),
    path("api/v1/", include("apps.modules.urls")),
    path("api/v1/", include("apps.crm.urls")),
    path("api/v1/", include("apps.erp.urls")),
    path("api/v1/", include("apps.hr.urls")),
    path("api/v1/", include("apps.inventory.urls")),
    path("api/v1/", include("apps.file_tracking.urls")),
    path("api/v1/", include("apps.projects.uce_urls")),
    path("api/v1/", include("apps.users.urls")),
    path("api/v1/", include("apps.webhooks.urls")),
    path("api/v1/", include("apps.ai_layer.urls")),
    path("api/", include("apps.server_monitor.urls")),
    path("api/", include("apps.hosting.urls")),
    path("api/", include("apps.api_keys.urls")),
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/v1/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
