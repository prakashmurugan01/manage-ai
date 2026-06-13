from channels.generic.websocket import AsyncJsonWebsocketConsumer


class DesktopTransferConsumer(AsyncJsonWebsocketConsumer):
    group_name = "desktop_transfer"

    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({"type": "desktop.connected", "message": "Desktop transfer stream connected."})

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        if content.get("type") == "ping":
            await self.send_json({"type": "pong"})

    async def desktop_event(self, event):
        await self.send_json(event["event"])
