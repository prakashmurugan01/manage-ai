from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .models import Notification
from .serializers import NotificationSerializer


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not user or user.is_anonymous:
            await self.close()
            return
        self.group_name = f"notifications_{user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json(await self.initial_payload(user))

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def notification_created(self, event):
        await self.send_json(event["payload"])

    async def new_notification(self, event):
        await self.send_json({"type": "new_notification", "notification": event["data"]})

    async def receive_json(self, content, **kwargs):
        action = content.get("action")
        user = self.scope["user"]
        if action == "mark_read":
            await self.mark_read(user, content.get("notification_id"))
        elif action == "mark_all_read":
            await self.mark_all_read(user)
        await self.send_json(await self.initial_payload(user))

    @database_sync_to_async
    def initial_payload(self, user):
        qs = Notification.objects.filter(recipient=user)
        return {
            "type": "notifications_initial",
            "unread_count": qs.filter(is_read=False).count(),
            "notifications": NotificationSerializer(qs.order_by("-urgency", "-created_at")[:10], many=True).data,
        }

    @database_sync_to_async
    def mark_read(self, user, notification_id):
        Notification.objects.filter(recipient=user, id=notification_id).update(is_read=True)

    @database_sync_to_async
    def mark_all_read(self, user):
        Notification.objects.filter(recipient=user, is_read=False).update(is_read=True)
