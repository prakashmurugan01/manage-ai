from rest_framework.routers import DefaultRouter

from apps.webhooks.views import DataSyncLogViewSet, EventViewSet

router = DefaultRouter()
router.register("events", EventViewSet, basename="uce-events")
router.register("sync-logs", DataSyncLogViewSet, basename="uce-sync-logs")

urlpatterns = router.urls

