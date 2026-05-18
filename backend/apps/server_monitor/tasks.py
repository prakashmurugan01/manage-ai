from datetime import timedelta
import time

import psutil
from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone

from apps.notifications.models import Notification

from .models import DiskMount, Server, ServerMetrics
from .serializers import ServerMetricsSerializer


def _gb(value):
    return round(value / (1024 ** 3), 2)


def _safe_cache_set(key, value, timeout):
    try:
        cache.set(key, value, timeout)
    except Exception:
        return False
    return True


@shared_task
def collect_server_metrics():
    servers = Server.objects.filter(is_enabled=True).order_by("id")
    payloads = []
    user = get_user_model().objects.filter(is_active=True).first()

    for server in servers:
        net = psutil.net_io_counters()
        boot_time = psutil.boot_time()
        uptime = int(time.time() - boot_time)
        cpu = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory().percent
        disk = psutil.disk_usage("/").percent
        metric = ServerMetrics.objects.create(
            server=server,
            cpu_percent=cpu,
            memory_percent=memory,
            disk_percent=disk,
            uptime_seconds=uptime,
            network_bytes_sent=net.bytes_sent,
            network_bytes_recv=net.bytes_recv,
        )
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except (PermissionError, FileNotFoundError, OSError):
                continue
            DiskMount.objects.create(
                server=server,
                mount_point=part.mountpoint,
                total_gb=_gb(usage.total),
                used_gb=_gb(usage.used),
                free_gb=_gb(usage.free),
                usage_percent=usage.percent,
            )
        data = ServerMetricsSerializer(metric).data
        _safe_cache_set(f"server:{server.id}:metrics", data, 120)
        payloads.append(data)
        if user and (cpu > 85 or memory > 90):
            Notification.objects.create(
                recipient=user,
                type="server_alert",
                urgency="warning",
                server=server,
                title=f"Server pressure on {server.name}",
                message=f"CPU {cpu:.1f}% and memory {memory:.1f}% on {server.ip_address}.",
            )

    _safe_cache_set("server_monitor:last10", payloads[-10:], 120)
    channel_layer = get_channel_layer()
    if channel_layer and payloads:
        try:
            async_to_sync(channel_layer.group_send)(
                "server_monitor",
                {"type": "server.metrics", "data": payloads},
            )
        except Exception:
            pass
    return len(payloads)


@shared_task
def check_disk_alerts():
    user = get_user_model().objects.filter(is_active=True).first()
    if not user:
        return 0
    count = 0
    since = timezone.now() - timedelta(hours=6)
    for server in Server.objects.filter(is_enabled=True):
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except (PermissionError, FileNotFoundError, OSError):
                continue
            previous = (
                DiskMount.objects.filter(server=server, mount_point=part.mountpoint)
                .order_by("-recorded_at")
                .first()
            )
            mount = DiskMount.objects.create(
                server=server,
                mount_point=part.mountpoint,
                total_gb=_gb(usage.total),
                used_gb=_gb(usage.used),
                free_gb=_gb(usage.free),
                usage_percent=usage.percent,
                alert_threshold=previous.alert_threshold if previous else 90,
            )
            if mount.usage_percent <= mount.alert_threshold:
                continue
            exists = Notification.objects.filter(
                server=server,
                type="disk_alert",
                urgency="critical",
                message__icontains=mount.mount_point,
                created_at__gte=since,
            ).exists()
            if exists:
                continue
            Notification.objects.create(
                recipient=user,
                type="disk_alert",
                urgency="critical",
                server=server,
                title=f"Disk alert on {server.name}",
                message=f"{mount.mount_point} is at {mount.usage_percent:.1f}% usage.",
            )
            count += 1
    return count
