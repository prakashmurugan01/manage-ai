from rest_framework import serializers

from apps.tasks.models import Task
from apps.tasks.serializers import TaskSerializer

from .models import TaskSuggestion


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
