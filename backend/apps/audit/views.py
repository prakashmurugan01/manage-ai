from rest_framework import filters, viewsets

from apps.core.permissions import IsSuperAdmin

from .models import APIRequestLog, AuditLog
from .serializers import APIRequestLogSerializer, AuditLogSerializer


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditLogSerializer
    permission_classes = [IsSuperAdmin]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["action", "entity_type", "entity_id", "actor__email", "path"]
    ordering_fields = ["created_at", "action", "entity_type"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return AuditLog.objects.select_related("actor")


class APIRequestLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = APIRequestLogSerializer
    permission_classes = [IsSuperAdmin]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["path", "method", "user__email"]
    ordering_fields = ["created_at", "duration_ms", "status_code"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return APIRequestLog.objects.select_related("user")
