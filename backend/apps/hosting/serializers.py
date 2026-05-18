from django.utils import timezone
from rest_framework import serializers

from .models import (
    DeploymentRun,
    DomainStatus,
    EmailAccount,
    HostedProject,
    HostingFailoverState,
    HostingApiUsageLog,
    HostingLifecycle,
    HostingLink,
    HostingProvider,
    HostingProjectApiKey,
    HostingStatus,
    ProjectUpload,
    VercelDeployment,
    VercelProject,
    VercelProjectLink,
)
from apps.api_keys.utils import _fernet, generate_api_key


class HostingLifecycleSerializer(serializers.ModelSerializer):
    performed_by_name = serializers.CharField(source="performed_by.get_full_name", read_only=True)

    class Meta:
        model = HostingLifecycle
        fields = "__all__"


class HostingApiUsageLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = HostingApiUsageLog
        fields = "__all__"


class HostingProjectApiKeySerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    plaintext_key = serializers.CharField(read_only=True)
    usage_count = serializers.IntegerField(source="usage_logs.count", read_only=True)

    class Meta:
        model = HostingProjectApiKey
        fields = [
            "id",
            "project",
            "project_name",
            "name",
            "key_prefix",
            "role",
            "permission_level",
            "rate_limit_per_minute",
            "is_active",
            "last_used_at",
            "expires_at",
            "created_by",
            "created_at",
            "updated_at",
            "plaintext_key",
            "usage_count",
        ]
        read_only_fields = ["key_prefix", "last_used_at", "created_by", "created_at", "updated_at"]

    def create(self, validated_data):
        plaintext, _, _ = generate_api_key()
        plaintext = plaintext.replace("uce_", "host_", 1)
        encrypted = _fernet().encrypt(plaintext.encode()).decode()
        obj = HostingProjectApiKey.objects.create(
            key_encrypted=encrypted,
            key_prefix=plaintext[5:17],
            created_by=self.context.get("request").user if self.context.get("request") else None,
            **validated_data,
        )
        obj.plaintext_key = plaintext
        HostingLifecycle.objects.create(project=obj.project, event_type=HostingLifecycle.Event.API_KEY_CREATED, performed_by=obj.created_by, notes=f"{obj.role} key created")
        return obj


class HostingProviderSerializer(serializers.ModelSerializer):
    link_count = serializers.IntegerField(source="links.count", read_only=True)

    class Meta:
        model = HostingProvider
        fields = "__all__"
        read_only_fields = ["last_synced_at", "last_error", "created_at", "updated_at"]


class HostingLinkSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    provider_name = serializers.CharField(source="provider_config.name", read_only=True)

    class Meta:
        model = HostingLink
        fields = "__all__"
        read_only_fields = [
            "response_time_ms",
            "uptime_percentage",
            "last_http_status",
            "last_checked_at",
            "last_failover_at",
            "created_at",
            "updated_at",
        ]


class EmailAccountSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    hosting_link_label = serializers.CharField(source="hosting_link.label", read_only=True)
    usage_percent = serializers.SerializerMethodField()

    class Meta:
        model = EmailAccount
        fields = "__all__"
        read_only_fields = ["used_mb", "mx_status", "last_checked_at", "created_at", "updated_at"]

    def get_usage_percent(self, obj):
        if not obj.quota_mb:
            return 0
        return round((obj.used_mb / obj.quota_mb) * 100, 2)

    def create(self, validated_data):
        obj = super().create(validated_data)
        HostingLifecycle.objects.create(project=obj.project, event_type=HostingLifecycle.Event.EMAIL_CREATED, notes=f"{obj.email} created.")
        return obj


class DomainStatusSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = DomainStatus
        fields = "__all__"
        read_only_fields = ["mx_records", "mx_status", "ssl_status", "ssl_expires_at", "email_health_score", "last_checked_at", "last_error", "metadata"]


class DeploymentRunSerializer(serializers.ModelSerializer):
    upload_name = serializers.CharField(source="upload.original_name", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = DeploymentRun
        fields = "__all__"
        read_only_fields = ["project", "status", "live_url", "logs", "progress", "error_message", "created_by", "created_at", "completed_at"]


class ProjectUploadSerializer(serializers.ModelSerializer):
    deployments = DeploymentRunSerializer(many=True, read_only=True)
    upload = serializers.FileField(write_only=True)

    class Meta:
        model = ProjectUpload
        fields = "__all__"
        read_only_fields = [
            "id",
            "owner",
            "project",
            "original_name",
            "size_bytes",
            "status",
            "project_type",
            "detected_stack",
            "suggested_providers",
            "analysis",
            "error_message",
            "created_at",
            "analyzed_at",
        ]

    def create(self, validated_data):
        file_obj = validated_data["upload"]
        obj = ProjectUpload.objects.create(
            owner=self.context.get("request").user if self.context.get("request") and self.context.get("request").user.is_authenticated else None,
            original_name=file_obj.name,
            size_bytes=file_obj.size,
            **validated_data,
        )
        return obj


class HostingFailoverStateSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    active_link_detail = HostingLinkSerializer(source="active_link", read_only=True)

    class Meta:
        model = HostingFailoverState
        fields = "__all__"
        read_only_fields = ["last_reason", "last_evaluated_at", "updated_at"]


class VercelProjectLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = VercelProjectLink
        fields = "__all__"
        read_only_fields = ["last_http_status", "response_time_ms", "uptime_percentage", "last_checked_at", "created_at"]


class VercelDeploymentSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = VercelDeployment
        fields = "__all__"
        read_only_fields = ["last_synced_at", "raw"]


class HostingStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = HostingStatus
        fields = "__all__"
        read_only_fields = ["last_action_at", "last_action_by"]


class VercelProjectSerializer(serializers.ModelSerializer):
    links = VercelProjectLinkSerializer(many=True, read_only=True)
    deployments = VercelDeploymentSerializer(many=True, read_only=True)
    hosting_status = HostingStatusSerializer(read_only=True)
    hosted_project_name = serializers.CharField(source="hosted_project.name", read_only=True)

    class Meta:
        model = VercelProject
        fields = "__all__"
        read_only_fields = [
            "vercel_id",
            "name",
            "account_id",
            "team_id",
            "framework",
            "production_domain",
            "latest_deployment_id",
            "latest_deployment_url",
            "latest_deployment_status",
            "raw",
            "last_synced_at",
            "created_at",
            "updated_at",
        ]


class HostedProjectSerializer(serializers.ModelSerializer):
    client_display_name = serializers.CharField(source="display_client_name", read_only=True)
    access_key = serializers.CharField(write_only=True, required=False, allow_blank=True)
    has_access_key = serializers.SerializerMethodField()
    days_remaining = serializers.SerializerMethodField()
    reminder_stage = serializers.SerializerMethodField()
    lifecycle = HostingLifecycleSerializer(many=True, read_only=True)
    api_key_count = serializers.IntegerField(source="api_keys.count", read_only=True)
    hosting_links = HostingLinkSerializer(many=True, read_only=True)
    email_accounts = EmailAccountSerializer(many=True, read_only=True)
    domain_status = DomainStatusSerializer(read_only=True)
    failover_state = HostingFailoverStateSerializer(read_only=True)

    class Meta:
        model = HostedProject
        fields = "__all__"
        read_only_fields = ["access_key_encrypted", "access_key_prefix", "last_checked_at", "downtime_count", "created_at"]

    def create(self, validated_data):
        access_key = validated_data.pop("access_key", "")
        obj = super().create(self._with_encrypted_key(validated_data, access_key))
        HostingLifecycle.objects.create(project=obj, event_type=HostingLifecycle.Event.CREATED, new_expiry=obj.expiry_date, new_platform=obj.hosting_platform)
        return obj

    def update(self, instance, validated_data):
        access_key = validated_data.pop("access_key", "")
        old_expiry = instance.expiry_date
        old_platform = instance.hosting_platform
        obj = super().update(instance, self._with_encrypted_key(validated_data, access_key))
        event = HostingLifecycle.Event.PLATFORM_CHANGED if old_platform != obj.hosting_platform else HostingLifecycle.Event.UPDATED
        HostingLifecycle.objects.create(
            project=obj,
            event_type=event,
            old_expiry=old_expiry,
            new_expiry=obj.expiry_date,
            old_platform=old_platform,
            new_platform=obj.hosting_platform,
            notes="Project details updated",
        )
        return obj

    def get_days_remaining(self, obj):
        return (obj.expiry_date - timezone.localdate()).days

    def get_has_access_key(self, obj):
        return bool(obj.access_key_encrypted)

    def get_reminder_stage(self, obj):
        days = self.get_days_remaining(obj)
        if days <= 1:
            return "critical"
        if days <= 7:
            return "urgent"
        if days <= 30:
            return "warning"
        if days <= 60:
            return "notice"
        return "healthy"

    def _with_encrypted_key(self, data, access_key):
        if access_key:
            if access_key == "__generate__":
                plaintext, encrypted, prefix = generate_api_key()
            else:
                plaintext = access_key
                encrypted = _fernet().encrypt(plaintext.encode()).decode()
                prefix = plaintext[:12]
            data["access_key_encrypted"] = encrypted
            data["access_key_prefix"] = prefix
        return data
