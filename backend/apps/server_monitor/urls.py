from rest_framework.routers import DefaultRouter

from .views import DiskMountViewSet, ServerMetricsViewSet, ServerViewSet

router = DefaultRouter()
router.register("servers", ServerViewSet, basename="servers")
router.register("server-metrics", ServerMetricsViewSet, basename="server-metrics")
router.register("disk-mounts", DiskMountViewSet, basename="disk-mounts")

urlpatterns = router.urls

