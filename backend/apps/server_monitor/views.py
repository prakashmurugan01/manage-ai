from datetime import timedelta
import platform
import socket

import psutil
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.functions import TruncHour
from django.db.models import Avg, Count
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import DiskMount, Server, ServerMetrics
from .serializers import DiskMountSerializer, ServerMetricsSerializer, ServerSerializer
from .tasks import collect_server_metrics


class ServerViewSet(viewsets.ModelViewSet):
    queryset = Server.objects.all()
    serializer_class = ServerSerializer
    search_fields = ["name", "ip_address", "description"]
    filterset_fields = ["status", "is_enabled"]
    ordering_fields = ["name", "created_at", "status"]

    @action(detail=False, methods=["get"])
    def summary(self, request):
        latest = ServerMetrics.objects.order_by("-recorded_at").first()
        status_counts = dict(Server.objects.values("status").annotate(total=Count("id")).values_list("status", "total"))
        return Response(
            {
                "servers": Server.objects.count(),
                "connected": status_counts.get(Server.Status.ACTIVE, 0),
                "offline": status_counts.get(Server.Status.DOWN, 0),
                "maintenance": status_counts.get(Server.Status.MAINTENANCE, 0),
                "last_metric_at": latest.recorded_at if latest else None,
                "latest_network": ServerMetricsSerializer(latest).data if latest else None,
            }
        )

    @action(detail=False, methods=["post"], url_path="discover-local")
    def discover_local(self, request):
        memory = psutil.virtual_memory()
        hostname = socket.gethostname()
        server, _ = Server.objects.update_or_create(
            ip_address="127.0.0.1",
            defaults={
                "name": request.data.get("name") or hostname,
                "hostname": hostname,
                "server_type": Server.ServerType.LOCAL,
                "connection_method": Server.ConnectionMethod.LOCAL,
                "ssh_port": 22,
                "status": Server.Status.ACTIVE,
                "is_enabled": True,
                "os_name": platform.system(),
                "os_version": platform.platform(),
                "cpu_cores": psutil.cpu_count(logical=True) or 0,
                "memory_total_gb": round(memory.total / (1024 ** 3), 2),
                "last_heartbeat_at": timezone.now(),
                "health_score": 100,
                "last_error": "",
            },
        )
        collect_server_metrics.delay()
        return Response(self.get_serializer(server).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="collect-now")
    def collect_now(self, request):
        result = collect_server_metrics.delay()
        return Response({"detail": "Metric collection queued.", "task_id": result.id})

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

    @action(detail=True, methods=["post"], url_path="ingest-metrics")
    def ingest_metrics(self, request, pk=None):
        server = self.get_object()
        payload = request.data.copy()
        allowed = {
            "cpu_percent",
            "cpu_temperature",
            "cpu_core_usage",
            "memory_percent",
            "memory_used_gb",
            "memory_free_gb",
            "memory_cached_gb",
            "disk_percent",
            "disk_read_bytes_per_sec",
            "disk_write_bytes_per_sec",
            "uptime_seconds",
            "network_bytes_sent",
            "network_bytes_recv",
            "upload_bytes_per_sec",
            "download_bytes_per_sec",
            "latency_ms",
            "packet_loss_percent",
            "process_count",
            "service_count",
        }
        metric_data = {key: payload[key] for key in allowed if key in payload}
        metric = ServerMetrics.objects.create(server=server, **metric_data)
        server.status = Server.Status.ACTIVE
        server.last_heartbeat_at = timezone.now()
        server.last_error = ""
        server.health_score = _metric_health_score(metric)
        for field in ["hostname", "os_name", "os_version", "cpu_cores", "memory_total_gb"]:
            if field in payload:
                setattr(server, field, payload[field])
        server.save(update_fields=["status", "last_heartbeat_at", "last_error", "health_score", "hostname", "os_name", "os_version", "cpu_cores", "memory_total_gb"])
        data = ServerMetricsSerializer(metric).data
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)("server_monitor", {"type": "server.metrics", "data": [data]})
            async_to_sync(channel_layer.group_send)("server_monitor", {"type": "server.updated", "data": ServerSerializer(server).data})
        return Response(data, status=status.HTTP_201_CREATED)


def _metric_health_score(metric):
    pressure = max(metric.cpu_percent or 0, metric.memory_percent or 0, metric.disk_percent or 0)
    if pressure >= 95:
        return 10
    if pressure >= 90:
        return 30
    if pressure >= 80:
        return 60
    if metric.packet_loss_percent >= 10:
        return 40
    return 100


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
