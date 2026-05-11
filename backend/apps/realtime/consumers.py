from channels.generic.websocket import AsyncJsonWebsocketConsumer


class UserEventConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return
        self.group_name = f"user_{user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({"type": "connected", "message": "Realtime channel ready"})

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def notification_created(self, event):
        await self.send_json({"type": "notification.created", "notification": event["notification"]})

    async def project_updated(self, event):
        await self.send_json({"type": event.get("event", "project.updated"), "project": event["project"]})

    async def task_progress(self, event):
        await self.send_json({"type": "task.progress", "task": event["task"]})

    async def collaboration_message(self, event):
        await self.send_json({"type": "collaboration.message", "message": event["message"]})

    async def collaboration_typing(self, event):
        await self.send_json({"type": "collaboration.typing", "typing": event["typing"]})


class TicketUpdateConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return
        self.ticket_id = self.scope["url_route"]["kwargs"]["ticket_id"]
        self.group_name = f"ticket_{self.ticket_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({"type": "connected", "ticket": self.ticket_id})

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def ticket_event(self, event):
        await self.send_json({"type": event.get("event", "ticket.updated"), "ticket": event["ticket"]})


class TicketListConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return
        organization_id = getattr(user, "company_id", None) or "global"
        self.group_name = f"ticket_list_{organization_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({"type": "connected", "scope": "tickets"})

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def ticket_event(self, event):
        await self.send_json({"type": event.get("event", "ticket.updated"), "ticket": event["ticket"]})
