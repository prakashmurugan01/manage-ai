from django.contrib.auth import get_user_model
from django.db.models import Count
from django.utils.dateparse import parse_date
from rest_framework import decorators, status, viewsets
from rest_framework.response import Response

from apps.core.mixins import AuditModelViewSetMixin
from apps.core.permissions import IsAdminLevel
from apps.hosting.models import HostedProject
from apps.server_monitor.models import Server

from .models import Notification
from .serializers import BroadcastNotificationSerializer, ManualNotificationSerializer, NotificationSerializer
from .services import notify_user
from .tasks import send_expiry_email

User = get_user_model()


class NotificationViewSet(AuditModelViewSetMixin, viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    audit_entity = "Notification"

    def get_permissions(self):
        if self.action in {"create", "broadcast"}:
            return [IsAdminLevel()]
        from rest_framework.permissions import IsAuthenticated

        return [IsAuthenticated()]

    def get_queryset(self):
        qs = Notification.objects.select_related("recipient", "sender", "project", "task", "hosted_project", "server").filter(recipient=self.request.user)
        params = self.request.query_params
        notification_type = params.get("type") or params.get("notification_type")
        urgency = params.get("urgency")
        is_read = params.get("is_read")
        date_from = params.get("date_from") or params.get("created_from")
        date_to = params.get("date_to") or params.get("created_to")
        if notification_type:
            qs = qs.filter(type=notification_type)
        if urgency:
            qs = qs.filter(urgency=urgency)
        if is_read is not None:
            qs = qs.filter(is_read=str(is_read).lower() in {"1", "true", "yes"})
        if date_from:
            parsed = parse_date(date_from)
            if parsed:
                qs = qs.filter(created_at__date__gte=parsed)
        if date_to:
            parsed = parse_date(date_to)
            if parsed:
                qs = qs.filter(created_at__date__lte=parsed)
        return qs

    def perform_create(self, serializer):
        serializer.save(sender=self.request.user)

    @decorators.action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=["is_read", "updated_at"])
        return Response(NotificationSerializer(notification, context={"request": request}).data)

    @decorators.action(detail=False, methods=["post"])
    def mark_all_read(self, request):
        updated = self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({"updated": updated, "unread_count": self.get_queryset().filter(is_read=False).count()})

    @decorators.action(detail=False, methods=["post"], url_path="send-manual")
    def send_manual(self, request):
        serializer = ManualNotificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project = None
        server = None
        project_id = serializer.validated_data.get("project_id")
        server_id = serializer.validated_data.get("server_id")
        if project_id:
            project = HostedProject.objects.filter(id=project_id).first()
            if not project:
                return Response({"project_id": "Hosted project not found."}, status=status.HTTP_400_BAD_REQUEST)
        if server_id:
            server = Server.objects.filter(id=server_id).first()
            if not server:
                return Response({"server_id": "Server not found."}, status=status.HTTP_400_BAD_REQUEST)
        notification = Notification.objects.create(
            recipient=request.user,
            sender=request.user,
            title=serializer.validated_data["title"],
            message=serializer.validated_data["message"],
            type=Notification.Type.MANUAL,
            urgency=serializer.validated_data["urgency"],
            hosted_project=project,
            server=server,
        )
        if serializer.validated_data.get("email"):
            send_expiry_email.delay(notification.id)
        return Response(NotificationSerializer(notification, context={"request": request}).data, status=status.HTTP_201_CREATED)

    @decorators.action(detail=False, methods=["post"], url_path="send")
    def send_manual_reminder(self, request):
        return self.send_manual(request)

    @decorators.action(detail=False, methods=["get"])
    def summary(self, request):
        qs = self.get_queryset()
        by_type = {row["type"]: row["count"] for row in qs.values("type").annotate(count=Count("id"))}
        return Response(
            {
                "unread_count": qs.filter(is_read=False).count(),
                "critical_count": qs.filter(urgency=Notification.Urgency.CRITICAL, is_read=False).count(),
                "by_type": by_type,
            }
        )

    @decorators.action(detail=False, methods=["post"], permission_classes=[IsAdminLevel])
    def broadcast(self, request):
        serializer = BroadcastNotificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        users = User.objects.filter(id__in=serializer.validated_data["recipients"])
        created = [
            notify_user(
                recipient=user,
                sender=request.user,
                title=serializer.validated_data["title"],
                message=serializer.validated_data["message"],
                type=serializer.validated_data["type"],
                urgency=serializer.validated_data["urgency"],
            )
            for user in users
        ]
        return Response(NotificationSerializer(created, many=True, context={"request": request}).data, status=status.HTTP_201_CREATED)
