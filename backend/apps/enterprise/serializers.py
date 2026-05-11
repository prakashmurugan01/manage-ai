from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.accounts.serializers import UserSerializer
from apps.core.permissions import Roles
from apps.projects.models import Project

from .models import (
    APIKey,
    APIKeyGrant,
    AuthenticationSettings,
    CloudStorageSettings,
    Company,
    CompanyService,
    CollaborationChannel,
    CollaborationMessage,
    ConnectionEvent,
    EmailEvent,
    FeatureFlag,
    HostingConnection,
    NetworkTelemetry,
    ProjectEstimate,
    ServerControlState,
    ServerFileAccess,
    SystemModuleControl,
    SystemSettingsAuditLog,
    UniversalConnector,
    UserAccessControl,
    VoiceCommandIntent,
)

User = get_user_model()


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = "__all__"
        read_only_fields = ("created_by", "created_at", "updated_at")


class CompanyServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyService
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")
        extra_kwargs = {"company": {"required": False}}


class UniversalConnectorSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)
    event_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = UniversalConnector
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at", "last_synced_at", "records_in", "records_out", "latency_ms", "last_error")
        extra_kwargs = {"company": {"required": False}}


class ConnectionEventSerializer(serializers.ModelSerializer):
    connector_name = serializers.CharField(source="connector.name", read_only=True)
    actor_email = serializers.EmailField(source="actor.email", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = ConnectionEvent
        fields = "__all__"
        read_only_fields = ("actor", "created_at", "updated_at")


class CollaborationChannelSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    member_count = serializers.SerializerMethodField()
    company = serializers.PrimaryKeyRelatedField(read_only=True)
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all(), required=False, allow_null=True)

    class Meta:
        model = CollaborationChannel
        fields = "__all__"
        read_only_fields = ("company", "created_at", "updated_at")

    def get_member_count(self, obj):
        return obj.members.count()


class CollaborationMessageSerializer(serializers.ModelSerializer):
    sender_detail = UserSerializer(source="sender", read_only=True)

    class Meta:
        model = CollaborationMessage
        fields = "__all__"
        read_only_fields = ("channel", "sender", "created_at", "updated_at", "attachment_name")


class FeatureFlagSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeatureFlag
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class APIKeyGrantSerializer(serializers.ModelSerializer):
    developer_detail = UserSerializer(source="developer", read_only=True)
    is_valid = serializers.BooleanField(read_only=True)

    class Meta:
        model = APIKeyGrant
        fields = ("id", "api_key", "developer", "developer_detail", "can_view", "can_use", "expires_at", "granted_by", "is_valid", "created_at", "updated_at")
        read_only_fields = ("granted_by", "created_at", "updated_at")

    def validate_developer(self, value):
        if value.role != Roles.DEVELOPER:
            raise serializers.ValidationError("API keys can only be granted to developer accounts.")
        return value


class APIKeySerializer(serializers.ModelSerializer):
    raw_key = serializers.CharField(write_only=True, required=False, allow_blank=False)
    grants = APIKeyGrantSerializer(many=True, read_only=True)

    class Meta:
        model = APIKey
        fields = ("id", "company", "name", "provider", "raw_key", "key_preview", "notes", "is_active", "created_by", "grants", "created_at", "updated_at")
        read_only_fields = ("key_preview", "created_by", "created_at", "updated_at")

    def create(self, validated_data):
        raw_key = validated_data.pop("raw_key")
        item = APIKey(**validated_data)
        item.set_raw_key(raw_key)
        item.created_by = self.context["request"].user
        item.save()
        return item

    def update(self, instance, validated_data):
        raw_key = validated_data.pop("raw_key", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if raw_key:
            instance.set_raw_key(raw_key)
        instance.save()
        return instance


class ProjectEstimateSerializer(serializers.ModelSerializer):
    client_detail = UserSerializer(source="client", read_only=True)
    total_cost = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = ProjectEstimate
        fields = "__all__"
        read_only_fields = ("created_by", "sent_at", "created_at", "updated_at")

    def validate_client(self, value):
        if value.role != Roles.CLIENT:
            raise serializers.ValidationError("Estimates must be assigned to a client account.")
        return value

    def validate_features(self, value):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


class EmailEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailEvent
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at", "sent_at")


class HostingConnectionSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = HostingConnection
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at", "last_deployed_at")


class ServerControlStateSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)
    storage_percent = serializers.SerializerMethodField()

    class Meta:
        model = ServerControlState
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at", "last_checked_at")

    def get_storage_percent(self, obj):
        if not obj.storage_total_gb:
            return 0
        return round(float(obj.storage_used_gb) / float(obj.storage_total_gb) * 100, 2)


class NetworkTelemetrySerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)

    class Meta:
        model = NetworkTelemetry
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")
        extra_kwargs = {"company": {"required": False}}


class VoiceCommandIntentSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)

    class Meta:
        model = VoiceCommandIntent
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")
        extra_kwargs = {"company": {"required": False}}


class SystemModuleControlSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)
    changed_by_detail = UserSerializer(source="changed_by", read_only=True)

    class Meta:
        model = SystemModuleControl
        fields = ("id", "company", "company_name", "module", "is_enabled", "description", "changed_by", "changed_by_detail", "changed_at", "created_at", "updated_at")
        read_only_fields = ("changed_by", "changed_at", "created_at", "updated_at")


class UserAccessControlSerializer(serializers.ModelSerializer):
    user_detail = UserSerializer(source="user", read_only=True)
    is_valid = serializers.BooleanField(read_only=True)
    granted_by_detail = UserSerializer(source="granted_by", read_only=True)

    class Meta:
        model = UserAccessControl
        fields = ("id", "company", "user", "user_detail", "module", "role", "actions", "is_enabled", "expires_at", "granted_by", "granted_by_detail", "is_valid", "created_at", "updated_at")
        read_only_fields = ("granted_by", "created_at", "updated_at")


class AuthenticationSettingsSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)
    updated_by_detail = UserSerializer(source="updated_by", read_only=True)

    class Meta:
        model = AuthenticationSettings
        fields = "__all__"
        read_only_fields = ("updated_by", "created_at", "updated_at")


class CloudStorageSettingsSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)
    updated_by_detail = UserSerializer(source="updated_by", read_only=True)
    usage_percent = serializers.FloatField(read_only=True)

    class Meta:
        model = CloudStorageSettings
        fields = ("id", "company", "company_name", "provider", "is_enabled", "endpoint_url", "bucket_name", "storage_limit_gb", "current_usage_gb", "file_count", "usage_percent", "is_backup_enabled", "last_backup_at", "updated_by", "updated_by_detail", "created_at", "updated_at")
        read_only_fields = ("access_key_hash", "current_usage_gb", "file_count", "updated_by", "created_at", "updated_at")


class ServerFileAccessSerializer(serializers.ModelSerializer):
    accessed_by_detail = UserSerializer(source="accessed_by", read_only=True)

    class Meta:
        model = ServerFileAccess
        fields = ("id", "company", "accessed_by", "accessed_by_detail", "file_path", "file_name", "file_size_bytes", "access_type", "is_success", "error_message", "ip_address", "created_at")
        read_only_fields = ("accessed_by", "created_at")


class SystemSettingsAuditLogSerializer(serializers.ModelSerializer):
    changed_by_detail = UserSerializer(source="changed_by", read_only=True)

    class Meta:
        model = SystemSettingsAuditLog
        fields = ("id", "company", "changed_by", "changed_by_detail", "entity_type", "entity_id", "action", "old_values", "new_values", "change_summary", "created_at")
        read_only_fields = ("created_at",)
