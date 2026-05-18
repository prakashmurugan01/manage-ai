from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.file_tracking.views import DiskTrackingDashboardView, DiskVolumeViewSet, FileAlertViewSet, FileEventViewSet, FileTransferViewSet, TrackingRuleViewSet

router = DefaultRouter()
router.register("file-tracking/volumes", DiskVolumeViewSet, basename="file-tracking-volumes")
router.register("file-tracking/transfers", FileTransferViewSet, basename="file-tracking-transfers")
router.register("file-tracking/events", FileEventViewSet, basename="file-tracking-events")
router.register("file-tracking/alerts", FileAlertViewSet, basename="file-tracking-alerts")
router.register("file-tracking/rules", TrackingRuleViewSet, basename="file-tracking-rules")

urlpatterns = [
    path("file-tracking/dashboard/", DiskTrackingDashboardView.as_view(), name="file-tracking-dashboard"),
] + router.urls

