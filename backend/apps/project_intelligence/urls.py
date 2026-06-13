from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AgentCommandViewSet,
    AgentIngestView,
    AgentRegistrationView,
    MachineAgentViewSet,
    ManagedProjectViewSet,
    ProjectIntelligenceDashboardView,
    ProjectLogEntryViewSet,
    ProjectWebhookEventViewSet,
    RuntimeMetricViewSet,
)

router = DefaultRouter()
router.register("project-agents", MachineAgentViewSet, basename="project-agents")
router.register("project-intelligence/projects", ManagedProjectViewSet, basename="project-intelligence-projects")
router.register("project-intelligence/metrics", RuntimeMetricViewSet, basename="project-intelligence-metrics")
router.register("project-intelligence/logs", ProjectLogEntryViewSet, basename="project-intelligence-logs")
router.register("project-intelligence/webhooks", ProjectWebhookEventViewSet, basename="project-intelligence-webhooks")
router.register("project-intelligence/commands", AgentCommandViewSet, basename="project-intelligence-commands")

urlpatterns = [
    path("project-intelligence/dashboard/", ProjectIntelligenceDashboardView.as_view(), name="project-intelligence-dashboard"),
    path("project-intelligence/agents/register/", AgentRegistrationView.as_view(), name="project-agent-register"),
    path("project-intelligence/agents/ingest/", AgentIngestView.as_view(), name="project-agent-ingest"),
    *router.urls,
]
