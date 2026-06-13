from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.core.views import CrossModuleQueryView, ModuleRegistryViewSet, UniversalQueryHistoryViewSet, UniversalQueryView

router = DefaultRouter()
router.register("query/history", UniversalQueryHistoryViewSet, basename="uce-query-history")
router.register("modules", ModuleRegistryViewSet, basename="uce-modules")

urlpatterns = [
    path("query/", UniversalQueryView.as_view(), name="uce-query"),
    path("query/cross/", CrossModuleQueryView.as_view(), name="uce-cross-query"),
] + router.urls

