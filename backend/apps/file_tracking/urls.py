from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.file_tracking.views import (
    ChunkUploadView,
    DesktopDeviceViewSet,
    DesktopTransferAuditLogViewSet,
    DesktopTransferJobViewSet,
    DesktopTransferSummaryView,
    DeviceConnectionViewSet,
    DiskTrackingDashboardView,
    DiskVolumeViewSet,
    FileAlertViewSet,
    FileEventViewSet,
    FileTransferViewSet,
    PhysicalStorageFileViewSet,
    ProjectFileViewSet,
    TrackingRuleViewSet,
)

router = DefaultRouter()
router.register("file-tracking/volumes", DiskVolumeViewSet, basename="file-tracking-volumes")
router.register("file-tracking/transfers", FileTransferViewSet, basename="file-tracking-transfers")
router.register("file-tracking/events", FileEventViewSet, basename="file-tracking-events")
router.register("file-tracking/alerts", FileAlertViewSet, basename="file-tracking-alerts")
router.register("file-tracking/rules", TrackingRuleViewSet, basename="file-tracking-rules")
router.register("file-transfer/devices", DesktopDeviceViewSet, basename="file-transfer-devices")
router.register("file-transfer/connections", DeviceConnectionViewSet, basename="file-transfer-connections")
router.register("file-transfer/files", ProjectFileViewSet, basename="file-transfer-files")
router.register("file-transfer/jobs", DesktopTransferJobViewSet, basename="file-transfer-jobs")
router.register("file-transfer/storage", PhysicalStorageFileViewSet, basename="file-transfer-storage")
router.register("file-transfer/audit-logs", DesktopTransferAuditLogViewSet, basename="file-transfer-audit-logs")

urlpatterns = [
    path("file-tracking/dashboard/", DiskTrackingDashboardView.as_view(), name="file-tracking-dashboard"),
    path("file-transfer/summary/", DesktopTransferSummaryView.as_view(), name="file-transfer-summary"),
    path("file-transfer/chunk-upload/", ChunkUploadView.as_view(), name="file-transfer-chunk-upload"),
] + router.urls
