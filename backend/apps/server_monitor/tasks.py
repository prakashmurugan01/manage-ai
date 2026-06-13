from datetime import timedelta
import platform
import socket
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
from .serializers import ServerMetricsSerializer, ServerSerializer


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
    server_payloads = []
    user = get_user_model().objects.filter(is_active=True).first()

    for server in servers:
        if _is_local_server(server):
            metric = _collect_local_metrics(server)
            data = ServerMetricsSerializer(metric).data
            _safe_cache_set(f"server:{server.id}:metrics", data, 120)
            payloads.append(data)
            if user and (metric.cpu_percent > 85 or metric.memory_percent > 90):
                Notification.objects.create(
                    recipient=user,
                    type="server_alert",
                    urgency="warning",
                    server=server,
                    title=f"Server pressure on {server.name}",
                    message=f"CPU {metric.cpu_percent:.1f}% and memory {metric.memory_percent:.1f}% on {server.ip_address}.",
                )
        else:
            _probe_remote_server(server)
        server_payloads.append(ServerSerializer(server).data)

    _safe_cache_set("server_monitor:last10", payloads[-10:], 120)
    channel_layer = get_channel_layer()
    if channel_layer and (payloads or server_payloads):
        try:
            async_to_sync(channel_layer.group_send)(
                "server_monitor",
                {"type": "server.metrics", "data": payloads},
            )
            async_to_sync(channel_layer.group_send)(
                "server_monitor",
                {"type": "server.updated", "data": server_payloads},
            )
        except Exception:
            pass
    return len(payloads)


def _is_local_server(server):
    if server.connection_method == Server.ConnectionMethod.LOCAL or server.server_type == Server.ServerType.LOCAL:
        return True
    return str(server.ip_address) in {"127.0.0.1", "::1"}


def _collect_local_metrics(server):
    net_before = psutil.net_io_counters()
    disk_before = psutil.disk_io_counters()
    cpu = psutil.cpu_percent(interval=1)
    core_usage = psutil.cpu_percent(interval=None, percpu=True)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    net_after = psutil.net_io_counters()
    disk_after = psutil.disk_io_counters()
    boot_time = psutil.boot_time()
    temperature = _cpu_temperature()
    server.hostname = socket.gethostname()
    server.os_name = platform.system()
    server.os_version = platform.platform()
    server.cpu_cores = psutil.cpu_count(logical=True) or 0
    server.memory_total_gb = _gb(memory.total)
    server.status = Server.Status.ACTIVE
    server.last_heartbeat_at = timezone.now()
    server.last_error = ""
    server.health_score = _health_score(cpu, memory.percent, disk.percent)
    server.save(update_fields=["hostname", "os_name", "os_version", "cpu_cores", "memory_total_gb", "status", "last_heartbeat_at", "last_error", "health_score"])
    metric = ServerMetrics.objects.create(
        server=server,
        cpu_percent=cpu,
        cpu_temperature=temperature,
        cpu_core_usage=[round(value, 2) for value in core_usage],
        memory_percent=memory.percent,
        memory_used_gb=_gb(memory.used),
        memory_free_gb=_gb(memory.available),
        memory_cached_gb=_gb(getattr(memory, "cached", 0)),
        disk_percent=disk.percent,
        disk_read_bytes_per_sec=max(0, (disk_after.read_bytes if disk_after else 0) - (disk_before.read_bytes if disk_before else 0)),
        disk_write_bytes_per_sec=max(0, (disk_after.write_bytes if disk_after else 0) - (disk_before.write_bytes if disk_before else 0)),
        uptime_seconds=int(time.time() - boot_time),
        network_bytes_sent=net_after.bytes_sent,
        network_bytes_recv=net_after.bytes_recv,
        upload_bytes_per_sec=max(0, net_after.bytes_sent - net_before.bytes_sent),
        download_bytes_per_sec=max(0, net_after.bytes_recv - net_before.bytes_recv),
        process_count=len(psutil.pids()),
        service_count=_service_count(),
    )
    _record_local_disks(server)
    return metric


def _record_local_disks(server):
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except (PermissionError, FileNotFoundError, OSError):
            continue
        previous = DiskMount.objects.filter(server=server, mount_point=part.mountpoint).order_by("-recorded_at").first()
        DiskMount.objects.create(
            server=server,
            mount_point=part.mountpoint,
            total_gb=_gb(usage.total),
            used_gb=_gb(usage.used),
            free_gb=_gb(usage.free),
            usage_percent=usage.percent,
            alert_threshold=previous.alert_threshold if previous else 90,
        )


def _probe_remote_server(server):
    started = time.perf_counter()
    port = server.ssh_port or _default_port(server.connection_method)
    try:
        with socket.create_connection((str(server.ip_address), port), timeout=3):
            pass
        latency = int((time.perf_counter() - started) * 1000)
        server.status = Server.Status.ACTIVE
        server.last_heartbeat_at = timezone.now()
        server.last_error = ""
        server.health_score = max(30, 100 - min(latency, 500) // 5)
        server.save(update_fields=["status", "last_heartbeat_at", "last_error", "health_score"])
    except OSError as exc:
        server.status = Server.Status.DOWN
        server.health_score = 0
        server.last_error = str(exc)
        server.save(update_fields=["status", "health_score", "last_error"])


def _default_port(method):
    return {
        Server.ConnectionMethod.SSH: 22,
        Server.ConnectionMethod.SFTP: 22,
        Server.ConnectionMethod.SMB: 445,
        Server.ConnectionMethod.WINRM: 5986,
        Server.ConnectionMethod.REST: 443,
        Server.ConnectionMethod.WEBSOCKET: 443,
    }.get(method, 22)


def _cpu_temperature():
    try:
        readings = psutil.sensors_temperatures()
    except Exception:
        return None
    for sensors in readings.values():
        for sensor in sensors:
            if sensor.current:
                return round(float(sensor.current), 2)
    return None


def _service_count():
    try:
        if hasattr(psutil, "win_service_iter"):
            return sum(1 for _ in psutil.win_service_iter())
    except Exception:
        return 0
    return 0


def _health_score(cpu, memory, disk):
    pressure = max(float(cpu or 0), float(memory or 0), float(disk or 0))
    if pressure >= 95:
        return 10
    if pressure >= 90:
        return 30
    if pressure >= 80:
        return 60
    return 100


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
