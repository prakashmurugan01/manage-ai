from datetime import timedelta

from django.db.models.functions import TruncHour
from django.db.models import Avg
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import DiskMount, Server, ServerMetrics
from .serializers import DiskMountSerializer, ServerMetricsSerializer, ServerSerializer


class ServerViewSet(viewsets.ModelViewSet):
    queryset = Server.objects.all()
    serializer_class = ServerSerializer
    search_fields = ["name", "ip_address", "description"]
    filterset_fields = ["status", "is_enabled"]
    ordering_fields = ["name", "created_at", "status"]

    @action(detail=True, methods=["get"])
    def metrics(self, request, pk=None):
        since = timezone.now() - timedelta(hours=int(request.query_params.get("hours", 24)))
        rows = self.get_object().metrics.filter(recorded_at__gte=since).order_by("recorded_at")
        return Response(ServerMetricsSerializer(rows, many=True).data)

    @action(detail=True, methods=["post"], url_path="toggle-power")
    def toggle_power(self, request, pk=None):
        server = self.get_object()
        server.is_enabled = not server.is_enabled
        server.status = Server.Status.ACTIVE if server.is_enabled else Server.Status.INACTIVE
        server.save(update_fields=["is_enabled", "status"])
        return Response(self.get_serializer(server).data)

    @action(detail=True, methods=["get"], url_path="metrics-history")
    def metrics_history(self, request, pk=None):
        since = timezone.now() - timedelta(hours=int(request.query_params.get("hours", 24)))
        rows = (
            self.get_object()
            .metrics.filter(recorded_at__gte=since)
            .annotate(hour=TruncHour("recorded_at"))
            .values("hour")
            .annotate(cpu_percent=Avg("cpu_percent"), memory_percent=Avg("memory_percent"), disk_percent=Avg("disk_percent"))
            .order_by("hour")
        )
        return Response(list(rows))

    @action(detail=True, methods=["get"], url_path="disk-history")
    def disk_history(self, request, pk=None):
        since = timezone.now() - timedelta(hours=int(request.query_params.get("hours", 24)))
        rows = self.get_object().disk_mounts.filter(recorded_at__gte=since).order_by("mount_point", "recorded_at")
        return Response(DiskMountSerializer(rows, many=True).data)

    @action(detail=True, methods=["get"])
    def disks(self, request, pk=None):
        rows = self.get_object().disk_mounts.order_by("-recorded_at")[:100]
        return Response(DiskMountSerializer(rows, many=True).data)


class ServerMetricsViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ServerMetrics.objects.select_related("server")
    serializer_class = ServerMetricsSerializer
    filterset_fields = ["server"]
    ordering_fields = ["recorded_at", "cpu_percent", "memory_percent", "disk_percent"]


class DiskMountViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DiskMount.objects.select_related("server")
    serializer_class = DiskMountSerializer
    filterset_fields = ["server", "mount_point"]
    ordering_fields = ["recorded_at", "usage_percent"]
