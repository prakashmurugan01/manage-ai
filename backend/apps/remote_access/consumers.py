import json
import struct

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.utils import timezone

from .models import RemoteActivityLog, RemoteDevice, RemoteSession
from .serializers import RemoteDeviceSerializer, RemoteSessionSerializer
from .views import log_action


class RemoteAgentConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.device = None
        token = self.scope.get("url_route", {}).get("kwargs", {}).get("token")
        self.device = await self.get_device(token)
        if not self.device:
            await self.close(code=4401)
            return
        self.device_group = f"remote_device_{self.device.id}"
        await self.channel_layer.group_add(self.device_group, self.channel_name)
        await self.accept()
        data = await self.mark_online()
        await self.broadcast_dashboard({"type": "device.online", "device": data})
        await self.send_json({"type": "agent.connected", "device": data})

    async def disconnect(self, close_code):
        if getattr(self, "device", None):
            await self.mark_offline()
            await self.channel_layer.group_discard(self.device_group, self.channel_name)
            await self.broadcast_dashboard({"type": "device.offline", "device_id": self.device.id})

    async def receive(self, text_data=None, bytes_data=None, **kwargs):
        if bytes_data is not None:
            await self.receive_binary(bytes_data)
            return
        if text_data is not None:
            await self.receive_json(json.loads(text_data), **kwargs)

    async def receive_binary(self, data):
        if len(data) < 4:
            return
        header_length = struct.unpack("!I", data[:4])[0]
        if len(data) < 4 + header_length:
            return
        try:
            header = json.loads(data[4 : 4 + header_length].decode("utf-8"))
        except json.JSONDecodeError:
            return
        token = header.get("session_token")
        if not token:
            return
        await self.channel_layer.group_send(
            f"remote_session_{token}",
            {"type": "session.binary", "bytes": data},
        )

    async def receive_json(self, content, **kwargs):
        kind = content.get("type")
        if kind == "heartbeat":
            await self.mark_online(content.get("metadata") or {})
        elif kind == "session.approved":
            session = await self.approve_session(content.get("session_token"), content.get("answer") or {})
            if session:
                await self.broadcast_session({"type": "session.approved", "session": session})
        elif kind == "session.denied":
            session = await self.deny_session(content.get("session_token"))
            if session:
                await self.broadcast_session({"type": "session.denied", "session": session})
        elif kind in {"screen.frame", "webrtc.signal", "file.result", "transfer.progress", "agent.error"}:
            await self.broadcast_session(content)

    async def device_message(self, event):
        await self.send_json(event["event"])

    async def broadcast_dashboard(self, event):
        await self.channel_layer.group_send("remote_access_dashboard", {"type": "dashboard.message", "event": event})

    async def broadcast_session(self, event):
        token = event.get("session_token") or event.get("session", {}).get("token")
        if token:
            await self.channel_layer.group_send(f"remote_session_{token}", {"type": "session.message", "event": event})
        await self.broadcast_dashboard(event)

    @database_sync_to_async
    def get_device(self, token):
        return RemoteDevice.objects.filter(token=token).first()

    @database_sync_to_async
    def mark_online(self, metadata=None):
        was_online = self.device.status == RemoteDevice.Status.ONLINE
        if metadata:
            self.device.metadata = {**self.device.metadata, **metadata}
            self.device.hostname = metadata.get("hostname") or self.device.hostname
            self.device.platform = metadata.get("platform") or self.device.platform
            self.device.agent_version = metadata.get("agent_version") or self.device.agent_version
            self.device.capabilities = metadata.get("capabilities") or self.device.capabilities
        self.device.status = RemoteDevice.Status.ONLINE
        self.device.last_seen_at = timezone.now()
        self.device.save(update_fields=["status", "last_seen_at", "hostname", "platform", "agent_version", "capabilities", "metadata", "updated_at"])
        if not was_online:
            log_action(RemoteActivityLog.Action.DEVICE_ONLINE, "Remote agent connected.", device=self.device)
        return RemoteDeviceSerializer(self.device).data

    @database_sync_to_async
    def mark_offline(self):
        self.device.status = RemoteDevice.Status.OFFLINE
        self.device.save(update_fields=["status", "updated_at"])
        log_action(RemoteActivityLog.Action.DEVICE_OFFLINE, "Remote agent disconnected.", device=self.device)

    @database_sync_to_async
    def approve_session(self, session_token, answer):
        session = RemoteSession.objects.filter(token=session_token, device=self.device).first()
        if not session:
            return None
        session.status = RemoteSession.Status.ACTIVE
        session.answer = answer
        session.approved_at = timezone.now()
        session.started_at = timezone.now()
        session.save(update_fields=["status", "answer", "approved_at", "started_at", "updated_at"])
        self.device.status = RemoteDevice.Status.BUSY
        self.device.save(update_fields=["status", "updated_at"])
        log_action(RemoteActivityLog.Action.SESSION_APPROVED, "Target approved remote session.", device=self.device, session=session)
        return RemoteSessionSerializer(session).data

    @database_sync_to_async
    def deny_session(self, session_token):
        session = RemoteSession.objects.filter(token=session_token, device=self.device).first()
        if not session:
            return None
        session.status = RemoteSession.Status.DENIED
        session.ended_at = timezone.now()
        session.save(update_fields=["status", "ended_at", "updated_at"])
        self.device.status = RemoteDevice.Status.ONLINE
        self.device.save(update_fields=["status", "updated_at"])
        log_action(RemoteActivityLog.Action.SESSION_DENIED, "Target denied remote session.", device=self.device, session=session)
        return RemoteSessionSerializer(session).data


class RemoteDashboardConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not user or user.is_anonymous:
            await self.close(code=4401)
            return
        self.user = user
        await self.channel_layer.group_add("remote_access_dashboard", self.channel_name)
        await self.accept()
        await self.send_json({"type": "dashboard.connected"})

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("remote_access_dashboard", self.channel_name)

    async def receive_json(self, content, **kwargs):
        kind = content.get("type")
        if kind == "join.session":
            token = content.get("session_token")
            if await self.can_join(token):
                await self.channel_layer.group_add(f"remote_session_{token}", self.channel_name)
                await self.send_json({"type": "session.joined", "session_token": token})
        elif kind == "session.command":
            session = await self.command_session(content.get("session_token"))
            if session:
                await self.channel_layer.group_send(
                    f"remote_device_{session['device_id']}",
                    {
                        "type": "device.message",
                        "event": {
                            "type": "session.command",
                            "session_token": session["token"],
                            "command": content.get("command"),
                            "payload": content.get("payload") or {},
                        },
                    },
                )

    async def dashboard_message(self, event):
        await self.send_json(event["event"])

    async def session_message(self, event):
        await self.send_json(event["event"])

    async def session_binary(self, event):
        await self.send(bytes_data=event["bytes"])

    @database_sync_to_async
    def can_join(self, token):
        return RemoteSession.objects.filter(token=token, requested_by=self.user).exists() or getattr(self.user, "role", None) in {"SUPER_ADMIN", "ADMIN"} or self.user.is_staff

    @database_sync_to_async
    def command_session(self, token):
        session = RemoteSession.objects.filter(token=token).select_related("requested_by").first()
        if not session:
            return None
        allowed = session.requested_by_id == self.user.id or getattr(self.user, "role", None) in {"SUPER_ADMIN", "ADMIN"} or self.user.is_staff
        if not allowed or session.status not in {RemoteSession.Status.APPROVED, RemoteSession.Status.ACTIVE}:
            return None
        return {"token": session.token, "device_id": session.device_id}
