from rest_framework import serializers

from apps.tasks.models import Task
from apps.tasks.serializers import TaskSerializer

from .models import AssistantAttachment, AssistantMessage, AssistantSession, TaskSuggestion


class TaskSuggestionSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = TaskSuggestion
        fields = (
            "id",
            "project",
            "project_name",
            "title",
            "description",
            "priority",
            "story_points",
            "confidence",
            "rationale",
            "status",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_by", "created_at", "updated_at")


class GenerateTaskSuggestionsSerializer(serializers.Serializer):
    project = serializers.IntegerField()
    context = serializers.CharField(required=False, allow_blank=True)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=10, default=6)


class ApproveSuggestionSerializer(serializers.Serializer):
    assignee = serializers.IntegerField(required=False)
    due_date = serializers.DateField(required=False)
    status = serializers.ChoiceField(choices=Task.Status.choices, required=False, default=Task.Status.BACKLOG)

    def to_representation(self, instance):
        return TaskSerializer(instance, context=self.context).data


class AssistantAttachmentSerializer(serializers.ModelSerializer):
    url = serializers.FileField(source="file", read_only=True)

    class Meta:
        model = AssistantAttachment
        fields = ("id", "original_name", "content_type", "size_bytes", "analysis", "url", "created_at")
        read_only_fields = fields


class AssistantMessageSerializer(serializers.ModelSerializer):
    attachments = AssistantAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = AssistantMessage
        fields = ("id", "session", "role", "content", "metadata", "attachments", "created_at", "updated_at")
        read_only_fields = ("id", "session", "role", "content", "metadata", "attachments", "created_at", "updated_at")


class AssistantSessionSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = AssistantSession
        fields = (
            "id",
            "title",
            "mode",
            "status",
            "project",
            "project_name",
            "model_provider",
            "model_name",
            "memory",
            "last_message",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("memory", "created_at", "updated_at", "last_message")

    def get_last_message(self, obj):
        message = obj.messages.order_by("-created_at").first()
        if not message:
            return ""
        return message.content[:180]


class AssistantChatSerializer(serializers.Serializer):
    message = serializers.CharField()
    session = serializers.IntegerField(required=False)
    project = serializers.IntegerField(required=False)
    mode = serializers.ChoiceField(choices=AssistantSession.Mode.choices, required=False, default=AssistantSession.Mode.GENERAL)
    voice = serializers.BooleanField(required=False, default=False)
    speak = serializers.BooleanField(required=False, default=False)
    model_provider = serializers.CharField(required=False, allow_blank=True, default="local")
    model_name = serializers.CharField(required=False, allow_blank=True, default="manageai-enterprise-local")
