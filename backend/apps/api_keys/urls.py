from rest_framework.routers import DefaultRouter
from django.urls import path

from .views import ApiKeyUsageLogViewSet, ApiKeyViewSet, ExternalIssueIngestView

router = DefaultRouter()
router.register("uce-api-keys", ApiKeyViewSet, basename="uce-api-keys")
router.register("uce-api-key-logs", ApiKeyUsageLogViewSet, basename="uce-api-key-logs")

urlpatterns = [
    path("external/issues/", ExternalIssueIngestView.as_view(), name="external-issue-ingest"),
    *router.urls,
]
