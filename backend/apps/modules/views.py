from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from rest_framework import permissions, viewsets

from apps.core.models import ModuleRegistry
from apps.core.views import api_response
from apps.modules.models import ConnectorDefinition
from apps.modules.serializers import ConnectorDefinitionSerializer


class ConnectorDefinitionViewSet(viewsets.ModelViewSet):
    serializer_class = ConnectorDefinitionSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = ConnectorDefinition.objects.filter(is_deleted=False)
    lookup_field = "module_id"
    ordering_fields = ["module_id", "created_at", "health_status"]
    search_fields = ["module_id", "display_name"]

    def perform_create(self, serializer):
        connector = serializer.save()
        ModuleRegistry.objects.update_or_create(
            module_id=connector.module_id,
            defaults={
                "display_name": connector.display_name,
                "version": "custom",
                "schema": connector.field_mappings,
                "capabilities": {"connection_type": connector.connection_type, "query_types": ["rest"]},
                "health_status": connector.health_status,
                "is_active": True,
            },
        )

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        return api_response(response.data, http_status=response.status_code)


def encrypt_secret(value):
    key = getattr(settings, "FIELD_ENCRYPTION_KEY", "")
    if not key or not value:
        return ""
    return Fernet(key.encode()).encrypt(value.encode()).decode()


def decrypt_secret(value):
    key = getattr(settings, "FIELD_ENCRYPTION_KEY", "")
    if not key or not value:
        return ""
    try:
        return Fernet(key.encode()).decrypt(value.encode()).decode()
    except InvalidToken:
        return ""

