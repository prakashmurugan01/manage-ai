from rest_framework import serializers

from .models import AgentCommand, DeploymentSignal, MachineAgent, ManagedProject, ProjectLogEntry, ProjectWebhookEvent, RuntimeMetric
from .services import create_agent


class MachineAgentSerializer(serializers.ModelSerializer):
    plaintext_token = serializers.CharField(read_only=True)
    project_count = serializers.SerializerMethodField()

    class Meta:
        model = MachineAgent
        exclude = ("token_hash",)
        read_only_fields = ("token_prefix", "status", "last_seen_at", "revoked_at", "created_at", "updated_at", "plaintext_token")

    def get_project_count(self, obj):
        annotated = getattr(obj, "project_count", None)
        if annotated is not None:
            return annotated
        if not obj.pk:
            return 0
        return obj.projects.count()


class AgentRegistrationSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=180)
    machine_id = serializers.CharField(max_length=160)
    environment = serializers.ChoiceField(choices=MachineAgent.Environment.choices, default=MachineAgent.Environment.DEVELOPMENT)
    hostname = serializers.CharField(max_length=255, required=False, allow_blank=True)
    os_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    capabilities = serializers.JSONField(required=False)
    metadata = serializers.JSONField(required=False)

    def create(self, validated_data):
        request = self.context["request"]
        return create_agent(request.user, **validated_data)


class RuntimeMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = RuntimeMetric
        fields = "__all__"


class ManagedProjectSerializer(serializers.ModelSerializer):
    agent_name = serializers.CharField(source="agent.name", read_only=True)
    agent_status = serializers.CharField(source="agent.status", read_only=True)
    latest_metric = serializers.SerializerMethodField()
    recent_error_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ManagedProject
        fields = "__all__"

    def get_latest_metric(self, obj):
        metric = getattr(obj, "latest_prefetched_metric", None)
        if isinstance(metric, list):
            metric = metric[0] if metric else None
        if not metric:
            metric = obj.metrics.first()
        return RuntimeMetricSerializer(metric).data if metric else None


class ProjectLogEntrySerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = ProjectLogEntry
        fields = "__all__"


class DeploymentSignalSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = DeploymentSignal
        fields = "__all__"


class ProjectWebhookEventSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = ProjectWebhookEvent
        fields = "__all__"


class AgentCommandSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = AgentCommand
        fields = "__all__"
        read_only_fields = ("status", "result", "sent_at", "completed_at", "created_at", "updated_at", "requested_by")
