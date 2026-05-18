from django.contrib.auth import get_user_model
from rest_framework import decorators, status, viewsets
from rest_framework.response import Response

from apps.core.mixins import AuditModelViewSetMixin
from apps.core.permissions import IsAdminLevel

from .models import Notification
from .serializers import BroadcastNotificationSerializer, NotificationSerializer
from .services import notify_user

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
        return Notification.objects.select_related("recipient", "sender", "project", "task", "hosted_project", "server").filter(recipient=self.request.user)

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
        return Response({"updated": updated})

    @decorators.action(detail=False, methods=["post"], url_path="send")
    def send_manual_reminder(self, request):
        notification = Notification.objects.create(
            recipient=request.user,
            sender=request.user,
            title=request.data.get("title", "Manual reminder"),
            message=request.data.get("message", ""),
            type=request.data.get("type", "maintenance"),
            urgency=request.data.get("urgency", "info"),
            hosted_project_id=request.data.get("project") or None,
        )
        return Response(NotificationSerializer(notification, context={"request": request}).data, status=status.HTTP_201_CREATED)

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
            )
            for user in users
        ]
        return Response(NotificationSerializer(created, many=True, context={"request": request}).data, status=status.HTTP_201_CREATED)
