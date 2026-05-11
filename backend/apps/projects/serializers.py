from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.accounts.serializers import TeamSerializer, UserSerializer
from apps.deployments.models import DeploymentControl
from apps.tasks.models import Task

from .models import Project, ProjectCommit
from .services import parse_github_repo_url, validate_local_url

User = get_user_model()


class ProjectSerializer(serializers.ModelSerializer):
    owner_detail = UserSerializer(source="owner", read_only=True)
    client_detail = UserSerializer(source="client", read_only=True)
    admins_detail = UserSerializer(source="admins", many=True, read_only=True)
    developers_detail = UserSerializer(source="developers", many=True, read_only=True)
    teams_detail = TeamSerializer(source="teams", many=True, read_only=True)
    task_count = serializers.IntegerField(read_only=True)
    open_task_count = serializers.IntegerField(read_only=True)
    commit_count = serializers.IntegerField(read_only=True)
    deployment_enabled = serializers.SerializerMethodField()
    latest_commit = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = (
            "id",
            "name",
            "company",
            "slug",
            "project_idea",
            "description",
            "technologies_used",
            "features_to_implement",
            "project_flow",
            "flow_generated_at",
            "status",
            "priority",
            "owner",
            "owner_detail",
            "client",
            "client_detail",
            "admins",
            "admins_detail",
            "developers",
            "developers_detail",
            "teams",
            "teams_detail",
            "start_date",
            "due_date",
            "workflow_days",
            "progress",
            "approval_status",
            "approval_note",
            "approved_by",
            "approved_at",
            "budget",
            "health_score",
            "repository_url",
            "local_repository_path",
            "connection_type",
            "connection_status",
            "connection_status_message",
            "local_url",
            "hosted_url",
            "github_owner",
            "github_repo",
            "github_default_branch",
            "selected_branch",
            "last_synced_at",
            "last_commit_sha",
            "last_commit_message",
            "last_commit_author",
            "last_commit_at",
            "tags",
            "task_count",
            "open_task_count",
            "commit_count",
            "deployment_enabled",
            "latest_commit",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "created_by",
            "progress",
            "health_score",
            "approved_by",
            "approved_at",
            "flow_generated_at",
            "connection_status",
            "connection_status_message",
            "last_synced_at",
            "last_commit_sha",
            "last_commit_message",
            "last_commit_author",
            "last_commit_at",
            "created_at",
            "updated_at",
        )
        extra_kwargs = {"owner": {"required": False}}

    def get_deployment_enabled(self, obj):
        deployment = getattr(obj, "deployment", None)
        return deployment.is_enabled if deployment else False

    def get_latest_commit(self, obj):
        commit = getattr(obj, "latest_prefetched_commit", None)
        if isinstance(commit, list):
            commit = commit[0] if commit else None
        if not commit and getattr(obj, "last_commit_sha", ""):
            return {
                "sha": obj.last_commit_sha,
                "message": obj.last_commit_message,
                "author_name": obj.last_commit_author,
                "committed_at": obj.last_commit_at,
            }
        if not commit:
            return None
        return ProjectCommitSerializer(commit).data

    def validate(self, attrs):
        client = attrs.get("client", getattr(self.instance, "client", None))
        if client and client.role != User.Role.CLIENT:
            raise serializers.ValidationError({"client": "Client must have CLIENT role."})
        owner = attrs.get("owner", getattr(self.instance, "owner", None))
        if owner and owner.role not in {User.Role.ADMIN, User.Role.SUPER_ADMIN}:
            raise serializers.ValidationError({"owner": "Owner must be an admin or super admin."})
        developers = attrs.get("developers")
        if developers:
            invalid_developers = [user.email for user in developers if user.role != User.Role.DEVELOPER]
            if invalid_developers:
                raise serializers.ValidationError({"developers": f"Only developer accounts can be assigned: {', '.join(invalid_developers)}"})
        admins = attrs.get("admins")
        if admins:
            invalid_admins = [user.email for user in admins if user.role not in {User.Role.ADMIN, User.Role.SUPER_ADMIN}]
            if invalid_admins:
                raise serializers.ValidationError({"admins": f"Only admin-level accounts can manage projects: {', '.join(invalid_admins)}"})
        workflow_days = attrs.get("workflow_days")
        if workflow_days is not None and not 1 <= workflow_days <= 365:
            raise serializers.ValidationError({"workflow_days": "Workflow days must be between 1 and 365."})
        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data.setdefault("created_by", request.user)
        project = super().create(validated_data)
        DeploymentControl.objects.get_or_create(project=project, defaults={"environment": "production"})
        return project


class ProjectCommitSerializer(serializers.ModelSerializer):
    short_sha = serializers.SerializerMethodField()

    class Meta:
        model = ProjectCommit
        fields = (
            "id",
            "project",
            "sha",
            "short_sha",
            "branch",
            "message",
            "author_name",
            "author_email",
            "author_login",
            "committed_at",
            "html_url",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_short_sha(self, obj):
        return obj.sha[:7]


class ProjectConnectionSerializer(serializers.Serializer):
    connection_type = serializers.ChoiceField(choices=Project.ConnectionType.choices)
    local_url = serializers.URLField(required=False, allow_blank=True)
    hosted_url = serializers.URLField(required=False, allow_blank=True)
    repository_url = serializers.URLField(required=False, allow_blank=True)
    local_repository_path = serializers.CharField(required=False, allow_blank=True, max_length=500)
    github_owner = serializers.CharField(required=False, allow_blank=True, max_length=120)
    github_repo = serializers.CharField(required=False, allow_blank=True, max_length=160)
    github_default_branch = serializers.CharField(required=False, allow_blank=True, max_length=120)
    selected_branch = serializers.CharField(required=False, allow_blank=True, max_length=120)

    def validate(self, attrs):
        connection_type = attrs.get("connection_type")
        if connection_type == Project.ConnectionType.LOCAL:
            local_url = attrs.get("local_url", "")
            if not local_url:
                raise serializers.ValidationError({"local_url": "Local URL is required."})
            validate_local_url(local_url)
        if connection_type == Project.ConnectionType.HOSTED and not attrs.get("hosted_url"):
            raise serializers.ValidationError({"hosted_url": "Hosted URL is required."})
        if connection_type == Project.ConnectionType.GITHUB:
            repository_url = attrs.get("repository_url", "")
            owner = attrs.get("github_owner", "")
            repo = attrs.get("github_repo", "")
            if repository_url and (not owner or not repo):
                parsed_owner, parsed_repo = parse_github_repo_url(repository_url)
                owner = owner or parsed_owner
                repo = repo or parsed_repo
                attrs["github_owner"] = owner
                attrs["github_repo"] = repo
            if not owner or not repo:
                raise serializers.ValidationError({"repository_url": "GitHub owner and repository are required."})
            attrs["selected_branch"] = attrs.get("selected_branch") or attrs.get("github_default_branch") or "main"
            attrs["github_default_branch"] = attrs.get("github_default_branch") or attrs["selected_branch"]
        return attrs

    def apply(self, project):
        data = self.validated_data
        connection_type = data["connection_type"]
        project.connection_type = connection_type
        project.connection_status_message = ""

        if connection_type == Project.ConnectionType.NONE:
            project.connection_status = Project.ConnectionStatus.DISCONNECTED
            project.local_url = ""
            project.hosted_url = ""
            project.repository_url = ""
            project.github_owner = ""
            project.github_repo = ""
            project.selected_branch = ""
        elif connection_type == Project.ConnectionType.LOCAL:
            project.connection_status = Project.ConnectionStatus.CONNECTED
            project.local_url = data["local_url"]
            project.hosted_url = ""
            project.repository_url = ""
            project.github_owner = ""
            project.github_repo = ""
            project.selected_branch = ""
        elif connection_type == Project.ConnectionType.HOSTED:
            project.connection_status = Project.ConnectionStatus.CONNECTED
            project.hosted_url = data["hosted_url"]
            project.local_url = ""
            project.repository_url = ""
            project.github_owner = ""
            project.github_repo = ""
            project.selected_branch = ""
        elif connection_type == Project.ConnectionType.GITHUB:
            project.connection_status = Project.ConnectionStatus.CONNECTED
            project.repository_url = data.get("repository_url", project.repository_url)
            project.local_repository_path = data.get("local_repository_path", project.local_repository_path)
            project.github_owner = data["github_owner"]
            project.github_repo = data["github_repo"]
            project.github_default_branch = data.get("github_default_branch") or "main"
            project.selected_branch = data.get("selected_branch") or project.github_default_branch

        project.save(
            update_fields=[
                "connection_type",
                "connection_status",
                "connection_status_message",
                "local_url",
                "hosted_url",
                "repository_url",
                "local_repository_path",
                "github_owner",
                "github_repo",
                "github_default_branch",
                "selected_branch",
                "updated_at",
            ]
        )
        return project


class BranchDeploySerializer(serializers.Serializer):
    branch = serializers.CharField(required=False, allow_blank=True, max_length=120)
    environment = serializers.ChoiceField(choices=DeploymentControl.Environment.choices, required=False)
    notes = serializers.CharField(required=False, allow_blank=True)


class GitPushSerializer(serializers.Serializer):
    branch = serializers.CharField(required=False, allow_blank=True, max_length=120)
    commit_message = serializers.CharField(required=False, allow_blank=True, max_length=240)


class ProjectApprovalSerializer(serializers.Serializer):
    approval_status = serializers.ChoiceField(choices=Project.ApprovalStatus.choices)
    approval_note = serializers.CharField(required=False, allow_blank=True)


class ProjectFlowSerializer(serializers.Serializer):
    prompt = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)
    flow = serializers.ListField(required=False, allow_empty=True)

    def validate_flow(self, value):
        for index, item in enumerate(value, start=1):
            if not isinstance(item, dict):
                raise serializers.ValidationError(f"Flow item {index} must be an object.")
            if not str(item.get("title", "")).strip():
                raise serializers.ValidationError(f"Flow item {index} requires a title.")
            if not str(item.get("key", "")).strip():
                item["key"] = f"step-{index}"
            item.setdefault("phase", index)
            item.setdefault("status", "READY")
            item.setdefault("activities", [])
            item.setdefault("inputs", [])
            item.setdefault("outputs", [])
        return value
