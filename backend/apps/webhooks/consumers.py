import json

from channels.generic.websocket import AsyncWebsocketConsumer


class UCEEventConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = "uce_events"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if text_data:
            data = json.loads(text_data)
            if data.get("type") == "ping":
                await self.send(text_data=json.dumps({"type": "pong"}))

    async def uce_event(self, event):
        await self.send(text_data=json.dumps({"type": "uce.event", "event": event["event"]}))

