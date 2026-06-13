from datetime import timedelta

from django.db.models import Avg, Count, Max, Prefetch, Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AgentCommand, DeploymentSignal, MachineAgent, ManagedProject, ProjectLogEntry, ProjectWebhookEvent, RuntimeMetric
from .serializers import (
    AgentCommandSerializer,
    AgentRegistrationSerializer,
    DeploymentSignalSerializer,
    MachineAgentSerializer,
    ManagedProjectSerializer,
    ProjectLogEntrySerializer,
    ProjectWebhookEventSerializer,
    RuntimeMetricSerializer,
)
from .services import AgentAuthenticationError, authenticate_agent_token, ingest_agent_payload, mark_stale_agents, request_ip


class VisibleProjectMixin:
    def visible_agents(self):
        qs = MachineAgent.objects.all()
        user = self.request.user
        if user.is_superuser:
            return qs
        return qs.filter(owner=user)

    def visible_projects(self):
        qs = ManagedProject.objects.select_related("agent", "linked_project")
        user = self.request.user
        if user.is_superuser:
            return qs
        return qs.filter(
            Q(agent__owner=user)
            | Q(linked_project__owner=user)
            | Q(linked_project__client=user)
            | Q(linked_project__created_by=user)
            | Q(linked_project__admins=user)
            | Q(linked_project__developers=user)
        ).distinct()


class AgentRegistrationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AgentRegistrationSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        agent = serializer.save()
        return Response(MachineAgentSerializer(agent).data, status=status.HTTP_201_CREATED)


class AgentIngestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        auth = request.headers.get("Authorization", "")
        token = auth.removeprefix("Agent ").strip() if auth.startswith("Agent ") else request.data.get("agent_token")
        try:
            agent = authenticate_agent_token(token)
        except AgentAuthenticationError as exc:
            return Response({"success": False, "error": str(exc)}, status=status.HTTP_401_UNAUTHORIZED)
        result = ingest_agent_payload(agent, request.data, ip_address=request_ip(request))
        return Response({"success": True, "data": result, "commands": self._commands(agent)}, status=status.HTTP_202_ACCEPTED)

    def _commands(self, agent):
        from .services import queued_commands_for

        return queued_commands_for(agent)


class ProjectIntelligenceDashboardView(VisibleProjectMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        mark_stale_agents()
        environment = request.query_params.get("environment") or "all"
        status_filter = request.query_params.get("status") or "all"
        window_hours = self._bounded_int(request.query_params.get("window_hours"), 24, 1, 720)
        since = timezone.now() - timedelta(hours=window_hours)

        agents = self.visible_agents()
        projects = self.visible_projects().prefetch_related(Prefetch("metrics", queryset=RuntimeMetric.objects.order_by("-recorded_at"), to_attr="latest_prefetched_metric"))
        if environment != "all":
            projects = projects.filter(environment=environment)
            agents = agents.filter(environment=environment)
        if status_filter != "all":
            projects = projects.filter(runtime_status=status_filter)

        project_ids = list(projects.values_list("id", flat=True))
        metrics = RuntimeMetric.objects.filter(project_id__in=project_ids, recorded_at__gte=since)
        unlinked_webhook_scope = Q(project__isnull=True) if request.user.is_superuser else Q(project__isnull=True, agent__in=agents)
        webhooks = ProjectWebhookEvent.objects.select_related("project", "agent").filter(Q(project_id__in=project_ids) | unlinked_webhook_scope, occurred_at__gte=since)
        logs = ProjectLogEntry.objects.select_related("project", "agent").filter(project_id__in=project_ids, timestamp__gte=since)
        deployments = DeploymentSignal.objects.select_related("project").filter(project_id__in=project_ids)

        response = {
            "generated_at": timezone.now().isoformat(),
            "window_hours": window_hours,
            "summary": self._summary(agents, projects, metrics, webhooks, logs),
            "agents": MachineAgentSerializer(agents.annotate(project_count=Count("projects")).order_by("name")[:200], many=True).data,
            "projects": ManagedProjectSerializer(projects.annotate(recent_error_count=Count("logs", filter=Q(logs__level__in=["error", "critical"]))).order_by("environment", "name")[:500], many=True).data,
            "traffic": self._traffic(metrics, since),
            "webhooks": ProjectWebhookEventSerializer(webhooks.order_by("-occurred_at")[:250], many=True).data,
            "logs": ProjectLogEntrySerializer(logs.order_by("-timestamp")[:250], many=True).data,
            "deployments": DeploymentSignalSerializer(deployments.order_by("-created_at")[:150], many=True).data,
            "topology": self._topology(agents, projects),
            "anomalies": self._anomalies(projects, webhooks, logs, metrics),
        }
        return Response(response)

    def _bounded_int(self, value, default, minimum, maximum):
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return default
        return max(minimum, min(maximum, parsed))

    def _summary(self, agents, projects, metrics, webhooks, logs):
        project_count = projects.count()
        webhook_count = webhooks.count()
        failed_webhooks = webhooks.filter(status__in=[ProjectWebhookEvent.Status.FAILED, ProjectWebhookEvent.Status.BLOCKED]).count()
        return {
            "agents_online": agents.filter(status=MachineAgent.Status.ONLINE).count(),
            "agents_total": agents.count(),
            "projects_total": project_count,
            "projects_running": projects.filter(runtime_status=ManagedProject.RuntimeStatus.RUNNING).count(),
            "projects_degraded": projects.filter(runtime_status__in=[ManagedProject.RuntimeStatus.DEGRADED, ManagedProject.RuntimeStatus.ERROR]).count(),
            "avg_cpu": round(metrics.aggregate(value=Avg("cpu_percent"))["value"] or 0, 2),
            "avg_memory": round(metrics.aggregate(value=Avg("memory_percent"))["value"] or 0, 2),
            "requests_per_second": round(metrics.aggregate(value=Avg("requests_per_second"))["value"] or 0, 2),
            "error_rate": round(metrics.aggregate(value=Avg("error_rate_percent"))["value"] or 0, 2),
            "webhook_events": webhook_count,
            "webhook_failures": failed_webhooks,
            "webhook_failure_rate": round((failed_webhooks / webhook_count) * 100, 2) if webhook_count else 0,
            "critical_logs": logs.filter(level__in=[ProjectLogEntry.Level.ERROR, ProjectLogEntry.Level.CRITICAL]).count(),
        }

    def _traffic(self, metrics, since):
        rows = []
        for metric in metrics.order_by("recorded_at")[:500]:
            rows.append(
                {
                    "time": metric.recorded_at.isoformat(),
                    "label": metric.recorded_at.strftime("%m/%d %H:%M"),
                    "cpu": metric.cpu_percent,
                    "memory": metric.memory_percent,
                    "rps": metric.requests_per_second,
                    "errors": metric.error_rate_percent,
                    "latency": metric.latency_ms,
                }
            )
        return rows or [{"time": since.isoformat(), "label": "No samples", "cpu": 0, "memory": 0, "rps": 0, "errors": 0, "latency": 0}]

    def _topology(self, agents, projects):
        nodes = []
        links = []
        for agent in agents[:200]:
            nodes.append({"id": str(agent.id), "type": "agent", "label": agent.name, "status": agent.status, "environment": agent.environment})
        for project in projects[:500]:
            nodes.append({"id": str(project.id), "type": "project", "label": project.name, "status": project.runtime_status, "environment": project.environment, "framework": project.framework})
            if project.agent_id:
                links.append({"source": str(project.agent_id), "target": str(project.id), "kind": "hosts"})
        return {"nodes": nodes, "links": links}

    def _anomalies(self, projects, webhooks, logs, metrics):
        anomalies = []
        unhealthy = projects.filter(health_score__lt=60).count()
        failed_webhooks = webhooks.filter(status__in=[ProjectWebhookEvent.Status.FAILED, ProjectWebhookEvent.Status.BLOCKED]).count()
        critical_logs = logs.filter(level__in=[ProjectLogEntry.Level.ERROR, ProjectLogEntry.Level.CRITICAL]).count()
        high_cpu = metrics.filter(cpu_percent__gte=90).values("project_id").distinct().count()
        if unhealthy:
            anomalies.append({"severity": "critical", "title": "Project health degradation", "detail": f"{unhealthy} projects are below the enterprise health threshold.", "recommendation": "Open impacted workspaces, review latest runtime metrics, and route incidents to owning teams."})
        if failed_webhooks:
            anomalies.append({"severity": "critical", "title": "Webhook processing failures", "detail": f"{failed_webhooks} webhook events failed or were blocked.", "recommendation": "Inspect payloads, signature validation, retry history, and downstream endpoint health."})
        if critical_logs:
            anomalies.append({"severity": "warning", "title": "Critical runtime log activity", "detail": f"{critical_logs} error or critical logs were captured in the selected window.", "recommendation": "Correlate logs with recent deployments and runtime resource saturation."})
        if high_cpu:
            anomalies.append({"severity": "warning", "title": "CPU saturation risk", "detail": f"{high_cpu} projects reported CPU above 90%.", "recommendation": "Scale workloads, check hot paths, and review active containers/processes."})
        if not anomalies:
            anomalies.append({"severity": "healthy", "title": "No active incident pattern detected", "detail": "Agents, projects, webhook events, and runtime telemetry are within normal bounds.", "recommendation": "Continue monitoring live topology and deployment risk signals."})
        return anomalies


class MachineAgentViewSet(VisibleProjectMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = MachineAgentSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["name", "machine_id", "hostname"]
    filterset_fields = ["status", "environment"]

    def get_queryset(self):
        return self.visible_agents().annotate(project_count=Count("projects"))

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        agent = self.get_object()
        agent.status = MachineAgent.Status.REVOKED
        agent.revoked_at = timezone.now()
        agent.save(update_fields=["status", "revoked_at", "updated_at"])
        return Response(self.get_serializer(agent).data)


class ManagedProjectViewSet(VisibleProjectMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = ManagedProjectSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["name", "framework", "current_branch", "repository_url"]
    filterset_fields = ["environment", "runtime_status", "build_status", "deployment_status", "framework"]

    def get_queryset(self):
        return self.visible_projects().prefetch_related(Prefetch("metrics", queryset=RuntimeMetric.objects.order_by("-recorded_at"), to_attr="latest_prefetched_metric"))

    @action(detail=True, methods=["get"])
    def workspace(self, request, pk=None):
        project = self.get_object()
        return Response(
            {
                "project": self.get_serializer(project).data,
                "metrics": RuntimeMetricSerializer(project.metrics.all()[:240], many=True).data,
                "logs": ProjectLogEntrySerializer(project.logs.all()[:150], many=True).data,
                "webhooks": ProjectWebhookEventSerializer(project.webhook_events.all()[:150], many=True).data,
                "deployments": DeploymentSignalSerializer(project.deployment_signals.all()[:80], many=True).data,
                "commands": AgentCommandSerializer(project.commands.all()[:80], many=True).data,
            }
        )

    @action(detail=True, methods=["post"])
    def command(self, request, pk=None):
        project = self.get_object()
        if not project.agent_id:
            return Response({"detail": "Project has no active agent."}, status=status.HTTP_409_CONFLICT)
        command = AgentCommand.objects.create(
            agent=project.agent,
            project=project,
            command_type=request.data.get("command_type") or AgentCommand.CommandType.REFRESH_DISCOVERY,
            payload=request.data.get("payload") or {},
            requested_by=request.user,
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        return Response(AgentCommandSerializer(command).data, status=status.HTTP_201_CREATED)


class RuntimeMetricViewSet(VisibleProjectMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = RuntimeMetricSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["project", "agent"]

    def get_queryset(self):
        return RuntimeMetric.objects.filter(project__in=self.visible_projects()).select_related("project", "agent")


class ProjectLogEntryViewSet(VisibleProjectMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = ProjectLogEntrySerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["project", "level", "source"]
    search_fields = ["message", "trace_id", "source", "project__name"]

    def get_queryset(self):
        return ProjectLogEntry.objects.filter(project__in=self.visible_projects()).select_related("project", "agent")


class ProjectWebhookEventViewSet(VisibleProjectMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = ProjectWebhookEventSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["project", "status", "direction", "integration", "event_type", "signature_valid"]
    search_fields = ["event_type", "integration", "project__name"]

    def get_queryset(self):
        unlinked_scope = Q(project__isnull=True)
        if not self.request.user.is_superuser:
            unlinked_scope = Q(project__isnull=True, agent__in=self.visible_agents())
        return ProjectWebhookEvent.objects.filter(Q(project__in=self.visible_projects()) | unlinked_scope).select_related("project", "agent")

    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        event = self.get_object()
        if not event.agent_id:
            return Response({"detail": "Webhook event has no agent execution context."}, status=status.HTTP_409_CONFLICT)
        command = AgentCommand.objects.create(
            agent=event.agent,
            project=event.project,
            command_type=AgentCommand.CommandType.REFRESH_DISCOVERY,
            payload={"action": "retry_webhook", "webhook_event_id": str(event.id), "event_type": event.event_type},
            requested_by=request.user,
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        return Response(AgentCommandSerializer(command).data, status=status.HTTP_201_CREATED)


class AgentCommandViewSet(VisibleProjectMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = AgentCommandSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["agent", "project", "status", "command_type"]

    def get_queryset(self):
        return AgentCommand.objects.filter(Q(project__in=self.visible_projects()) | Q(agent__in=self.visible_agents())).select_related("agent", "project", "requested_by").distinct()
