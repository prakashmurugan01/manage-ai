from rest_framework import serializers

from .models import ApiKey, ApiKeyUsageLog
from .utils import generate_api_key


class ApiKeyUsageLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApiKeyUsageLog
        fields = "__all__"


class ApiKeySerializer(serializers.ModelSerializer):
    plaintext_key = serializers.CharField(read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = ApiKey
        fields = [
            "id",
            "project",
            "project_name",
            "name",
            "key_prefix",
            "role",
            "rate_limit_per_minute",
            "expires_at",
            "is_active",
            "ip_whitelist",
            "last_used_at",
            "created_at",
            "updated_at",
            "plaintext_key",
        ]
        read_only_fields = ["key_prefix", "last_used_at", "created_at", "updated_at"]

    def create(self, validated_data):
        plaintext, encrypted, prefix, key_hash = generate_api_key(include_hash=True)
        obj = ApiKey.objects.create(key_encrypted="", key_hash=key_hash, key_prefix=prefix, **validated_data)
        obj.plaintext_key = plaintext
        return obj
