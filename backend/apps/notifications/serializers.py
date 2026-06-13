from rest_framework import serializers

from apps.accounts.serializers import UserSerializer

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(source="recipient", read_only=True)
    notification_type = serializers.CharField(source="type", required=False)
    is_emailed = serializers.BooleanField(source="is_sent_email", read_only=True)
    related_project = serializers.PrimaryKeyRelatedField(source="hosted_project", read_only=True)
    related_server = serializers.PrimaryKeyRelatedField(source="server", read_only=True)
    sender_detail = UserSerializer(source="sender", read_only=True)

    class Meta:
        model = Notification
        fields = (
            "id",
            "user",
            "recipient",
            "sender",
            "sender_detail",
            "notification_type",
            "title",
            "message",
            "type",
            "urgency",
            "is_read",
            "is_emailed",
            "is_sent_email",
            "project",
            "task",
            "related_project",
            "hosted_project",
            "related_server",
            "server",
            "days_threshold",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("sender", "created_at", "updated_at")


class BroadcastNotificationSerializer(serializers.Serializer):
    recipients = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)
    title = serializers.CharField(max_length=200)
    message = serializers.CharField()
    type = serializers.ChoiceField(choices=Notification.Type.choices, default=Notification.Type.INFO)
    urgency = serializers.ChoiceField(choices=Notification.Urgency.choices, default=Notification.Urgency.INFO)
    project = serializers.IntegerField(required=False)
    task = serializers.IntegerField(required=False)


class ManualNotificationSerializer(serializers.Serializer):
    project_id = serializers.IntegerField(required=False, allow_null=True)
    server_id = serializers.IntegerField(required=False, allow_null=True)
    urgency = serializers.ChoiceField(choices=Notification.Urgency.choices, default=Notification.Urgency.INFO)
    title = serializers.CharField(max_length=200)
    message = serializers.CharField()
    email = serializers.BooleanField(default=False)
