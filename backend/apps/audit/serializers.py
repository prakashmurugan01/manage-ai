from rest_framework import serializers

from apps.accounts.serializers import UserSerializer

from .models import APIRequestLog, AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actor_detail = UserSerializer(source="actor", read_only=True)

    class Meta:
        model = AuditLog
        fields = "__all__"


class APIRequestLogSerializer(serializers.ModelSerializer):
    user_detail = UserSerializer(source="user", read_only=True)

    class Meta:
        model = APIRequestLog
        fields = "__all__"
