from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.core.permissions import Roles, has_role

from .models import Team

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="get_full_name", read_only=True)
    assigned_project_count = serializers.SerializerMethodField()
    assigned_task_count = serializers.SerializerMethodField()
    open_ticket_count = serializers.SerializerMethodField()
    assigned_projects = serializers.SerializerMethodField()
    assigned_tasks = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "username",
            "company",
            "first_name",
            "last_name",
            "full_name",
            "role",
            "approval_status",
            "rejection_reason",
            "approved_by",
            "approved_at",
            "suspended_at",
            "department",
            "phone",
            "avatar",
            "secret_id",
            "role_title",
            "skills",
            "bio",
            "availability_status",
            "face_login_enabled",
            "face_enrolled_at",
            "face_security_checks",
            "assigned_project_count",
            "assigned_task_count",
            "open_ticket_count",
            "assigned_projects",
            "assigned_tasks",
            "is_active",
            "last_login",
            "last_seen_at",
            "date_joined",
        )
        read_only_fields = ("id", "secret_id", "approved_by", "approved_at", "suspended_at", "face_enrolled_at", "last_login", "last_seen_at", "date_joined")

    def get_assigned_project_count(self, obj):
        if obj.role == User.Role.DEVELOPER:
            return obj.developer_projects.count()
        if obj.role == User.Role.CLIENT:
            return obj.client_projects.count()
        return obj.owned_projects.count() + obj.admin_projects.count()

    def get_assigned_task_count(self, obj):
        return obj.assigned_tasks.exclude(status="DONE").count()

    def get_open_ticket_count(self, obj):
        return obj.assigned_tickets.exclude(status__in=["RESOLVED", "CLOSED"]).count()

    def get_assigned_projects(self, obj):
        if obj.role == User.Role.DEVELOPER:
            projects = obj.developer_projects.all()[:6]
        elif obj.role == User.Role.CLIENT:
            projects = obj.client_projects.all()[:6]
        else:
            projects = (obj.owned_projects.all() | obj.admin_projects.all()).distinct()[:6]
        return [
            {
                "id": project.id,
                "name": project.name,
                "status": project.status,
                "progress": project.progress,
                "priority": project.priority,
            }
            for project in projects
        ]

    def get_assigned_tasks(self, obj):
        tasks = obj.assigned_tasks.select_related("project").exclude(status="DONE")[:8]
        return [
            {
                "id": task.id,
                "title": task.title,
                "status": task.status,
                "workflow_day": task.workflow_day,
                "approval_status": task.approval_status,
                "project_name": task.project.name,
            }
            for task in tasks
        ]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    role = serializers.ChoiceField(choices=User.Role.choices, required=False, default=User.Role.CLIENT)

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "username",
            "password",
            "first_name",
            "last_name",
            "role",
            "phone",
            "avatar",
            "department",
            "role_title",
            "skills",
            "bio",
            "availability_status",
        )

    def validate_role(self, value):
        request = self.context.get("request")
        if value in {Roles.SUPER_ADMIN, Roles.ADMIN} and not has_role(getattr(request, "user", None), Roles.SUPER_ADMIN):
            raise serializers.ValidationError("Only Super Admins can create admin-level accounts.")
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.approval_status = User.ApprovalStatus.PENDING
        user.is_active = True
        user.set_password(password)
        user.save()
        return user


class UserWriteSerializer(UserSerializer):
    password = serializers.CharField(write_only=True, required=False, validators=[validate_password])

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ("password",)
        read_only_fields = ("id", "secret_id", "approved_by", "approved_at", "suspended_at", "face_enrolled_at", "last_login", "last_seen_at", "date_joined")

    def validate_role(self, value):
        request = self.context.get("request")
        if value in {Roles.SUPER_ADMIN, Roles.ADMIN} and not has_role(getattr(request, "user", None), Roles.SUPER_ADMIN):
            raise serializers.ValidationError("Only Super Admins can assign admin-level roles.")
        return value

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = User.EMAIL_FIELD

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["email"] = user.email
        token["name"] = user.get_full_name() or user.email
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user, context=self.context).data
        return data


class TeamSerializer(serializers.ModelSerializer):
    lead_detail = UserSerializer(source="lead", read_only=True)
    members_detail = UserSerializer(source="members", many=True, read_only=True)
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = (
            "id",
            "name",
            "company",
            "description",
            "lead",
            "lead_detail",
            "members",
            "members_detail",
            "member_count",
            "max_members",
            "is_active",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_by", "created_at", "updated_at")

    def get_member_count(self, obj):
        return obj.members.count()

    def validate(self, attrs):
        lead = attrs.get("lead", getattr(self.instance, "lead", None))
        members = attrs.get("members")
        max_members = attrs.get("max_members", getattr(self.instance, "max_members", 50))
        if lead and lead.role != User.Role.DEVELOPER:
            raise serializers.ValidationError({"lead": "Team lead must be a developer."})
        if members:
            invalid = [user.email for user in members if user.role != User.Role.DEVELOPER]
            if invalid:
                raise serializers.ValidationError({"members": f"Only developers can be team members: {', '.join(invalid)}"})
            if len(members) > max_members:
                raise serializers.ValidationError({"members": f"Team limit is {max_members} members."})
        return attrs
