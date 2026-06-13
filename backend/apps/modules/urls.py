from rest_framework.routers import DefaultRouter

from apps.modules.views import ConnectorDefinitionViewSet

router = DefaultRouter()
router.register("modules/connectors", ConnectorDefinitionViewSet, basename="uce-connectors")

urlpatterns = router.urls

