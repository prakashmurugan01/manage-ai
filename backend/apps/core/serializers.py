from rest_framework import serializers

from apps.core.models import ModuleRegistry, UniversalQuery


class UniversalQueryRequestSerializer(serializers.Serializer):
    input = serializers.CharField()
    type = serializers.ChoiceField(choices=["sql", "rest", "nl", "natural_language"], required=False, default="nl")
    modules = serializers.ListField(child=serializers.SlugField(), required=False, allow_empty=True)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=500, default=50)
    offset = serializers.IntegerField(required=False, min_value=0, default=0)

    def validate_type(self, value):
        return "nl" if value == "natural_language" else value


class UniversalQuerySerializer(serializers.ModelSerializer):
    class Meta:
        model = UniversalQuery
        fields = [
            "query_id",
            "raw_input",
            "query_type",
            "normalized_iql",
            "target_modules",
            "executed_at",
            "execution_ms",
            "result_count",
            "created_at",
        ]


class ModuleRegistrySerializer(serializers.ModelSerializer):
    class Meta:
        model = ModuleRegistry
        fields = [
            "module_id",
            "display_name",
            "version",
            "schema",
            "capabilities",
            "endpoints",
            "is_active",
            "last_health_check",
            "health_status",
            "registered_at",
        ]

