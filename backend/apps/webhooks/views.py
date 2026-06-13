from rest_framework import permissions

from apps.modules.api import BaseModuleViewSet
from apps.webhooks.models import DataSyncLog, Event
from apps.webhooks.serializers import DataSyncLogSerializer, EventSerializer


class EventViewSet(BaseModuleViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["event_type", "source_module", "entity_type", "entity_id"]
    ordering_fields = ["created_at", "processed_at"]


class DataSyncLogViewSet(BaseModuleViewSet):
    queryset = DataSyncLog.objects.all()
    serializer_class = DataSyncLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["source_module", "target_module", "entity_id"]
    ordering_fields = ["created_at", "resolved_at"]

