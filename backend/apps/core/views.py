from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import ModuleRegistry, UniversalQuery
from apps.core.serializers import ModuleRegistrySerializer, UniversalQueryRequestSerializer, UniversalQuerySerializer
from apps.core.services import UniversalQueryProcessor


def api_response(data=None, meta=None, errors=None, http_status=status.HTTP_200_OK):
    return Response(
        {
            "success": not errors,
            "data": data if data is not None else {},
            "meta": meta or {},
            "errors": errors or [],
        },
        status=http_status,
    )


class UniversalQueryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = UniversalQueryRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        result = UniversalQueryProcessor().execute(
            raw_input=payload["input"],
            query_type=payload["type"],
            modules=payload.get("modules"),
            limit=payload["limit"],
            offset=payload["offset"],
            user=request.user,
        )
        return api_response(result)


class CrossModuleQueryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        query = request.query_params.get("query", "")
        result = UniversalQueryProcessor().execute(
            raw_input=query,
            query_type="nl",
            modules=None,
            limit=int(request.query_params.get("limit", 50)),
            offset=int(request.query_params.get("offset", 0)),
            user=request.user,
        )
        return api_response(result)


class UniversalQueryHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UniversalQuerySerializer
    permission_classes = [permissions.IsAuthenticated]
    ordering_fields = ["created_at", "execution_ms", "result_count"]
    search_fields = ["raw_input"]

    def get_queryset(self):
        queryset = UniversalQuery.objects.filter(is_deleted=False)
        if not self.request.user.is_staff:
            queryset = queryset.filter(created_by=self.request.user)
        return queryset


class ModuleRegistryViewSet(viewsets.ModelViewSet):
    queryset = ModuleRegistry.objects.filter(is_deleted=False)
    serializer_class = ModuleRegistrySerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "module_id"
    ordering_fields = ["module_id", "health_status", "registered_at"]
    search_fields = ["module_id", "display_name"]

    @action(detail=True, methods=["get"])
    def health(self, request, module_id=None):
        module = self.get_object()
        return api_response(
            {
                "module_id": module.module_id,
                "status": module.health_status,
                "last_health_check": module.last_health_check,
                "active": module.is_active,
            }
        )

