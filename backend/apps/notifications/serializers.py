from rest_framework import serializers

from apps.accounts.serializers import UserSerializer

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    sender_detail = UserSerializer(source="sender", read_only=True)

    class Meta:
        model = Notification
        fields = (
            "id",
            "recipient",
            "sender",
            "sender_detail",
            "title",
            "message",
            "type",
            "is_read",
            "project",
            "task",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("sender", "created_at", "updated_at")


class BroadcastNotificationSerializer(serializers.Serializer):
    recipients = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)
    title = serializers.CharField(max_length=160)
    message = serializers.CharField()
    type = serializers.ChoiceField(choices=Notification.Type.choices, default=Notification.Type.INFO)
    project = serializers.IntegerField(required=False)
    task = serializers.IntegerField(required=False)
