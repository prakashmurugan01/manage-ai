from datetime import timedelta

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.core.cache import cache
from django.utils import timezone

from .models import Server, ServerMetrics
from .serializers import ServerMetricsSerializer, ServerSerializer


class ServerMonitorConsumer(AsyncJsonWebsocketConsumer):
    group_name = "server_monitor"

    async def connect(self):
        if not self.scope.get("user") or self.scope["user"].is_anonymous:
            await self.close(code=4001)
            return
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({"type": "initial", "servers": await self.get_initial_servers(), "metrics": await self.get_last_metrics()})

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        action = content.get("action")
        if action == "toggle_server":
            server = await self.toggle_server(content.get("server_id"), content.get("enabled"))
            await self.channel_layer.group_send(self.group_name, {"type": "server.updated", "data": server})
        elif action == "get_history":
            data = await self.get_history(content.get("server_id"), int(content.get("hours", 24)))
            await self.send_json({"type": "history", "server_id": content.get("server_id"), "metrics": data})

    async def server_metrics(self, event):
        await self.send_json({"type": "metrics_update", "metrics": event["data"]})

    async def server_updated(self, event):
        await self.send_json({"type": "server_updated", "server": event["data"]})

    @database_sync_to_async
    def get_initial_servers(self):
        return ServerSerializer(Server.objects.all(), many=True).data

    @database_sync_to_async
    def get_last_metrics(self):
        try:
            cached = cache.get("server_monitor:last10")
        except Exception:
            cached = None
        if cached:
            return cached
        rows = ServerMetrics.objects.select_related("server").order_by("-recorded_at")[:10]
        data = ServerMetricsSerializer(rows, many=True).data
        try:
            cache.set("server_monitor:last10", data, 120)
        except Exception:
            pass
        return data

    @database_sync_to_async
    def toggle_server(self, server_id, enabled):
        server = Server.objects.get(id=server_id)
        server.is_enabled = bool(enabled)
        server.status = Server.Status.ACTIVE if server.is_enabled else Server.Status.INACTIVE
        server.save(update_fields=["is_enabled", "status"])
        return ServerSerializer(server).data

    @database_sync_to_async
    def get_history(self, server_id, hours):
        since = timezone.now() - timedelta(hours=hours)
        rows = ServerMetrics.objects.filter(server_id=server_id, recorded_at__gte=since).order_by("recorded_at")
        return ServerMetricsSerializer(rows, many=True).data
