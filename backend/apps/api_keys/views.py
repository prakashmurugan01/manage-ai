from datetime import timedelta

from django.db.models import Avg, Count
from django.db.models.functions import TruncHour
from django.utils import timezone
from django.core.cache import cache
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tickets.models import Ticket
from apps.tickets.serializers import TicketSerializer
from apps.webhooks.models import Event

from .models import ApiKey, ApiKeyUsageLog
from .serializers import ApiKeySerializer, ApiKeyUsageLogSerializer
from .utils import generate_api_key


class ApiKeyViewSet(viewsets.ModelViewSet):
    queryset = ApiKey.objects.select_related("project")
    serializer_class = ApiKeySerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["project", "role", "is_active"]
    search_fields = ["name", "key_prefix", "project__name"]

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if not user.is_authenticated:
            return qs.none()
        if user.is_superuser:
            return qs
        return qs.filter(project__owner=user)

    def perform_create(self, serializer):
        project = serializer.validated_data["project"]
        if not self._can_manage(project):
            raise PermissionDenied("Only the project owner can manage API keys.")
        serializer.save()

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        response.data["warning"] = "Store this key securely. It will not be shown again."
        return response

    def perform_update(self, serializer):
        if not self._can_manage(serializer.instance.project):
            raise PermissionDenied("Only the project owner can manage API keys.")
        serializer.save()

    @action(detail=True, methods=["post"])
    def regenerate(self, request, pk=None):
        api_key = self.get_object()
        if not self._can_manage(api_key.project):
            raise PermissionDenied("Only the project owner can manage API keys.")
        plaintext, encrypted, prefix, key_hash = generate_api_key(include_hash=True)
        api_key.key_encrypted = ""
        api_key.key_hash = key_hash
        api_key.key_prefix = prefix
        api_key.save(update_fields=["key_encrypted", "key_hash", "key_prefix", "updated_at"])
        data = self.get_serializer(api_key).data
        data["plaintext_key"] = plaintext
        data["warning"] = "Store this key securely. It will not be shown again."
        return Response(data)

    @action(detail=True, methods=["post"])
    def toggle(self, request, pk=None):
        api_key = self.get_object()
        if not self._can_manage(api_key.project):
            raise PermissionDenied("Only the project owner can manage API keys.")
        api_key.is_active = not api_key.is_active
        api_key.save(update_fields=["is_active", "updated_at"])
        return Response(self.get_serializer(api_key).data)

    @action(detail=True, methods=["get"])
    def usage_stats(self, request, pk=None):
        since = timezone.now() - timedelta(hours=24)
        hourly = (
            ApiKeyUsageLog.objects.filter(api_key=self.get_object(), timestamp__gte=since)
            .annotate(hour=TruncHour("timestamp"))
            .values("hour")
            .annotate(count=Count("id"), avg_response_ms=Avg("response_time_ms"))
            .order_by("hour")
        )
        redis_counts = {}
        try:
            client = cache.client.get_client()
            now_minute = int(timezone.now().timestamp() // 60)
            for minute in range(now_minute - 59, now_minute + 1):
                redis_counts[str(minute)] = client.zcard(f"api_requests:{minute}")
        except Exception:
            redis_counts = {}
        return Response({"hourly": list(hourly), "redis_recent_minutes": redis_counts})

    @action(detail=True, methods=["get"])
    def logs(self, request, pk=None):
        logs = self.get_object().usage_logs.all()[:100]
        return Response(ApiKeyUsageLogSerializer(logs, many=True).data)

    @action(detail=True, methods=["get"])
    def usage(self, request, pk=None):
        return self.usage_stats(request, pk)

    def _can_manage(self, project):
        user = self.request.user
        request_key = getattr(self.request, "api_key", None)
        if request_key and request_key.role == ApiKey.Role.VIEWER:
            return False
        return user.is_superuser or project.owner_id == user.id


class ApiKeyUsageLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ApiKeyUsageLog.objects.select_related("api_key", "api_key__project")
    serializer_class = ApiKeyUsageLogSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["api_key", "http_method", "response_code"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated:
            return qs.none()
        if user.is_superuser:
            return qs
        return qs.filter(api_key__project__owner=user)


class ExternalIssueIngestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        api_key = getattr(request, "api_key", None)
        project = getattr(request, "project_scope", None)
        if not api_key or not project:
            return Response({"success": False, "error": "Invalid Token", "detail": "Authorization: API_KEY <key> is required."}, status=status.HTTP_401_UNAUTHORIZED)

        payload_type = str(request.data.get("type") or request.data.get("event_type") or "query").lower()
        source_platform = request.data.get("source_platform") or request.data.get("source") or api_key.name
        external_id = request.data.get("external_id") or request.data.get("conversation_id") or request.data.get("message_id")
        incoming_status = request.data.get("status")
        ticket_ref = request.data.get("ticket_id") or request.data.get("ticket")

        if payload_type in {"status_update", "ticket_update", "update"} or ticket_ref:
            ticket = self._find_ticket(project, ticket_ref, external_id)
            if not ticket:
                return Response({"success": False, "error": "Server Down", "detail": "Ticket could not be found for update."}, status=status.HTTP_404_NOT_FOUND)
            ticket_status = self._normalize_ticket_status(incoming_status)
            if ticket_status:
                old_status = ticket.status
                ticket.status = ticket_status
                ticket.custom_fields = {
                    **(ticket.custom_fields or {}),
                    "source_platform": source_platform,
                    "external_id": external_id,
                    "last_external_update": timezone.now().isoformat(),
                    "external_status": incoming_status,
                }
                ticket.save(update_fields=["status", "custom_fields", "updated_at"])
                Event.objects.create(
                    event_type="external_issue.updated",
                    source_module=str(source_platform)[:50],
                    entity_type="ticket",
                    entity_id=str(ticket.id),
                    payload={
                        "title": ticket.title,
                        "project": project.id,
                        "ticket_id": ticket.ticket_id,
                        "source_platform": source_platform,
                        "external_id": external_id,
                        "status": ticket.status,
                        "previous_status": old_status,
                        "raw": request.data,
                    },
                )
            return Response({"success": True, "status": ticket.status.lower(), "data": TicketSerializer(ticket).data})

        title = request.data.get("title") or request.data.get("issue") or request.data.get("query") or "External chatbot query"
        description = request.data.get("description") or request.data.get("details") or request.data.get("message") or request.data.get("complaint") or ""
        priority = Ticket.normalize_priority(str(request.data.get("priority") or "P3").upper())

        event = Event.objects.create(
            event_type="external_issue.created",
            source_module=str(source_platform)[:50],
            entity_type="project",
            entity_id=str(project.id),
            payload={
                "title": title,
                "description": description,
                "source_platform": source_platform,
                "project": project.id,
                "external_id": external_id,
                "message_type": payload_type,
                "status": "open",
                "raw": request.data,
            },
        )
        ticket = Ticket.objects.create(
            project=project,
            title=title[:220],
            description=description or title,
            priority=priority,
            status=Ticket.Status.OPEN,
            source=Ticket.Source.SYSTEM,
            custom_fields={
                "source_platform": source_platform,
                "event_id": str(event.id),
                "external_id": external_id,
                "message_type": payload_type,
                "api_key": api_key.key_prefix,
            },
        )
        event.payload = {
            **event.payload,
            "ticket_id": ticket.ticket_id,
            "ticket": ticket.id,
            "ticket_status": ticket.status,
            "project_name": project.name,
        }
        event.save(update_fields=["payload"])
        return Response(
            {
                "success": True,
                "status": "open",
                "data": {
                    "ticket_id": ticket.ticket_id,
                    "ticket": ticket.id,
                    "event": event.id,
                    "project": project.id,
                    "source_platform": source_platform,
                },
            },
            status=status.HTTP_201_CREATED,
        )

    def _find_ticket(self, project, ticket_ref, external_id):
        qs = Ticket.objects.filter(project=project)
        if ticket_ref:
            ticket = qs.filter(ticket_id=ticket_ref).first()
            if not ticket:
                try:
                    ticket = qs.filter(id=int(ticket_ref)).first()
                except (TypeError, ValueError):
                    ticket = None
            if ticket:
                return ticket
        if external_id:
            return qs.filter(custom_fields__external_id=external_id).first()
        return None

    def _normalize_ticket_status(self, value):
        normalized = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
        aliases = {
            "OPEN": Ticket.Status.OPEN,
            "NEW": Ticket.Status.OPEN,
            "IN_PROGRESS": Ticket.Status.IN_PROGRESS,
            "PROGRESS": Ticket.Status.IN_PROGRESS,
            "PENDING": Ticket.Status.PENDING,
            "RESOLVED": Ticket.Status.RESOLVED,
            "CLOSED": Ticket.Status.CLOSED,
        }
        return aliases.get(normalized)
