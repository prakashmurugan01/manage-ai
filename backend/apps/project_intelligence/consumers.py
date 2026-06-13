from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .services import AgentAuthenticationError, authenticate_agent_token, ingest_agent_payload, queued_commands_for


class ProjectIntelligenceConsumer(AsyncJsonWebsocketConsumer):
    group_name = "project_intelligence"

    async def connect(self):
        user = self.scope.get("user")
        if not user or user.is_anonymous:
            await self.close()
            return
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def project_event(self, event):
        await self.send_json(event["event"])


class ProjectAgentConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        query = parse_qs(self.scope.get("query_string", b"").decode())
        token = (query.get("token") or [""])[0]
        try:
            self.agent = await database_sync_to_async(authenticate_agent_token)(token)
        except AgentAuthenticationError:
            await self.close()
            return
        await self.accept()
        await self.send_json({"type": "agent.accepted", "agent_id": str(self.agent.id)})

    async def receive_json(self, content, **kwargs):
        kind = content.get("type")
        if kind in {"heartbeat", "snapshot", "telemetry"}:
            result = await database_sync_to_async(ingest_agent_payload)(self.agent, content.get("payload") or content)
            commands = await database_sync_to_async(queued_commands_for)(self.agent)
            await self.send_json({"type": "ingest.accepted", "data": result, "commands": commands})
        elif kind == "command.result":
            await self._record_command_result(content)
        else:
            await self.send_json({"type": "agent.warning", "message": f"Unsupported message type: {kind}"})

    @database_sync_to_async
    def _record_command_result(self, content):
        from django.utils import timezone

        from .models import AgentCommand

        command_id = content.get("command_id")
        command = AgentCommand.objects.filter(id=command_id, agent=self.agent).first()
        if not command:
            return
        command.status = AgentCommand.Status.SUCCEEDED if content.get("success", False) else AgentCommand.Status.FAILED
        command.result = content.get("result") or {}
        command.completed_at = timezone.now()
        command.save(update_fields=["status", "result", "completed_at", "updated_at"])
