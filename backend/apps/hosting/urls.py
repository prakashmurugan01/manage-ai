from rest_framework.routers import DefaultRouter
from django.urls import path

from .views import (
    DeploymentRunViewSet,
    DomainStatusViewSet,
    EmailAccountViewSet,
    HostedProjectViewSet,
    HostingFailoverViewSet,
    HostingLifecycleViewSet,
    HostingLinkViewSet,
    HostingProjectApiKeyViewSet,
    HostingProviderViewSet,
    NetlifyRedeployView,
    NetlifyStatusView,
    ProjectUploadViewSet,
    UnifiedHostingProviderView,
    VercelDeploymentViewSet,
    VercelProjectViewSet,
)

router = DefaultRouter()
router.register("hosting/providers", HostingProviderViewSet, basename="hosting-providers")
router.register("hosting/links", HostingLinkViewSet, basename="hosting-links")
router.register("hosting/email-accounts", EmailAccountViewSet, basename="hosting-email-accounts")
router.register("hosting/domain-status", DomainStatusViewSet, basename="hosting-domain-status")
router.register("hosting/uploads", ProjectUploadViewSet, basename="hosting-uploads")
router.register("hosting/deployments", DeploymentRunViewSet, basename="hosting-deployments")
router.register("hosting/failover", HostingFailoverViewSet, basename="hosting-failover")
router.register("hosting-lifecycle", HostingLifecycleViewSet, basename="hosting-lifecycle")
router.register("hosting-api-keys", HostingProjectApiKeyViewSet, basename="hosting-api-keys")
router.register("email/manage", EmailAccountViewSet, basename="email-manage")
router.register("vercel/projects", VercelProjectViewSet, basename="vercel-projects")
router.register("vercel/deployments", VercelDeploymentViewSet, basename="vercel-deployments")
router.register("hosting", HostedProjectViewSet, basename="hosting")

urlpatterns = [
    path("netlify-status/", NetlifyStatusView.as_view(), name="netlify-status"),
    path("netlify/redeploy/", NetlifyRedeployView.as_view(), name="netlify-redeploy"),
    path("hosting/providers/<str:provider>/projects/", UnifiedHostingProviderView.as_view(), name="hosting-provider-projects"),
    path("hosting/providers/<str:provider>/sync/", UnifiedHostingProviderView.as_view(), {"operation": "sync"}, name="hosting-provider-sync"),
    path("hosting/providers/<str:provider>/projects/<str:project_id>/", UnifiedHostingProviderView.as_view(), name="hosting-provider-project-detail"),
    path("hosting/providers/<str:provider>/projects/<str:project_id>/<str:operation>/", UnifiedHostingProviderView.as_view(), name="hosting-provider-project-operation"),
    *router.urls,
]
