from rest_framework import serializers

from apps.modules.models import ConnectorDefinition


class ConnectorDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConnectorDefinition
        fields = [
            "id",
            "module_id",
            "display_name",
            "connection_type",
            "base_url",
            "auth_type",
            "field_mappings",
            "sync_frequency",
            "health_status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "health_status", "created_at", "updated_at"]

