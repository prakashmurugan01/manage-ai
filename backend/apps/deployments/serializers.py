from rest_framework import serializers

from apps.accounts.serializers import UserSerializer

from .models import DeploymentControl, DeploymentHistory, DeploymentRecord


class DeploymentHistorySerializer(serializers.ModelSerializer):
    actor_detail = UserSerializer(source="actor", read_only=True)

    class Meta:
        model = DeploymentHistory
        fields = ("id", "is_enabled", "status", "version", "actor", "actor_detail", "notes", "created_at")


class DeploymentControlSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    toggled_by_detail = UserSerializer(source="toggled_by", read_only=True)
    history = DeploymentHistorySerializer(many=True, read_only=True)

    class Meta:
        model = DeploymentControl
        fields = (
            "id",
            "project",
            "project_name",
            "environment",
            "is_enabled",
            "status",
            "version",
            "source_branch",
            "commit_sha",
            "last_deployed_at",
            "toggled_by",
            "toggled_by_detail",
            "notes",
            "history",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("toggled_by", "last_deployed_at", "created_at", "updated_at")


class DeploymentToggleSerializer(serializers.Serializer):
    is_enabled = serializers.BooleanField()
    version = serializers.CharField(required=False, allow_blank=True, max_length=80)
    source_branch = serializers.CharField(required=False, allow_blank=True, max_length=120)
    commit_sha = serializers.CharField(required=False, allow_blank=True, max_length=80)
    notes = serializers.CharField(required=False, allow_blank=True)


class DeploymentRecordSerializer(serializers.ModelSerializer):
    project_detail_name = serializers.CharField(source="project.name", read_only=True)
    hosted_project_name = serializers.CharField(source="hosted_project.name", read_only=True)
    assigned_developer_detail = UserSerializer(source="assigned_developer", read_only=True)
    created_by_detail = UserSerializer(source="created_by", read_only=True)

    class Meta:
        model = DeploymentRecord
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")
