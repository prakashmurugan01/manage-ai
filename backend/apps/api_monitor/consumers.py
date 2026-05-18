from channels.generic.websocket import AsyncJsonWebsocketConsumer


class ApiMonitorConsumer(AsyncJsonWebsocketConsumer):
    group_name = "api_monitor"

    async def connect(self):
        if not self.scope.get("user") or self.scope["user"].is_anonymous:
            await self.close()
            return
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def api_stats(self, event):
        await self.send_json(event["payload"])

