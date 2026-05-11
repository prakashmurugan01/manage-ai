from rest_framework import serializers

from apps.accounts.serializers import UserSerializer
from apps.core.permissions import Roles, has_role

from .models import Task, TaskComment


class TaskSerializer(serializers.ModelSerializer):
    assignee_detail = UserSerializer(source="assignee", read_only=True)
    reporter_detail = UserSerializer(source="reporter", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = Task
        fields = (
            "id",
            "project",
            "project_name",
            "title",
            "description",
            "status",
            "priority",
            "assignee",
            "assignee_detail",
            "reporter",
            "reporter_detail",
            "due_date",
            "estimated_hours",
            "logged_hours",
            "story_points",
            "workflow_day",
            "progress_percent",
            "day_progress",
            "delay_reason",
            "completion_note",
            "approval_status",
            "approved_by",
            "approved_at",
            "completed_at",
            "review_note",
            "depends_on",
            "workflow_loop_key",
            "ai_suggested",
            "position",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("reporter", "approved_by", "approved_at", "completed_at", "created_at", "updated_at")

    def validate(self, attrs):
        request = self.context.get("request")
        if request and has_role(request.user, Roles.DEVELOPER):
            allowed = {"status", "logged_hours", "position", "workflow_day", "progress_percent", "day_progress", "delay_reason", "completion_note"}
            invalid = set(attrs) - allowed
            if invalid:
                raise serializers.ValidationError("Developers can only update status, logged hours, workflow progress, delay reason, completion note, and board position.")
        workflow_day = attrs.get("workflow_day")
        if workflow_day is not None and not 1 <= workflow_day <= 365:
            raise serializers.ValidationError({"workflow_day": "Workflow day must be between 1 and 365."})
        progress_percent = attrs.get("progress_percent")
        if progress_percent is not None and not 0 <= progress_percent <= 100:
            raise serializers.ValidationError({"progress_percent": "Progress must be between 0 and 100."})
        return attrs


class KanbanMoveSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Task.Status.choices)
    position = serializers.IntegerField(min_value=0)


class TaskCommentSerializer(serializers.ModelSerializer):
    author_detail = UserSerializer(source="author", read_only=True)

    class Meta:
        model = TaskComment
        fields = ("id", "task", "author", "author_detail", "body", "is_internal", "created_at", "updated_at")
        read_only_fields = ("author", "created_at", "updated_at")
