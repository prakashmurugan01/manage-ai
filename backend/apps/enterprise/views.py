from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from rest_framework import decorators, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAdminLevel, Roles, has_role, is_admin_level
from apps.deployments.models import DeploymentControl
from apps.documents.models import Document
from apps.notifications.services import notify_user
from apps.projects.models import Project
from apps.tasks.models import Task
from apps.tickets.models import Ticket

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
from .reporting import make_pdf, make_xlsx
from .serializers import (
    APIKeyGrantSerializer,
    APIKeySerializer,
    AuthenticationSettingsSerializer,
    CloudStorageSettingsSerializer,
    CompanySerializer,
    CompanyServiceSerializer,
    CollaborationChannelSerializer,
    CollaborationMessageSerializer,
    ConnectionEventSerializer,
    EmailEventSerializer,
    FeatureFlagSerializer,
    HostingConnectionSerializer,
    NetworkTelemetrySerializer,
    ProjectEstimateSerializer,
    ServerControlStateSerializer,
    ServerFileAccessSerializer,
    SystemModuleControlSerializer,
    SystemSettingsAuditLogSerializer,
    UniversalConnectorSerializer,
    UserAccessControlSerializer,
    VoiceCommandIntentSerializer,
)
from .services import send_automation_email

User = get_user_model()


def scoped_company(user):
    return getattr(user, "company", None)


def ensure_company(user):
    company = scoped_company(user)
    if company:
        return company
    company, _ = Company.objects.get_or_create(
        slug="primary-company",
        defaults={"name": "Primary Company", "description": "Default isolated company workspace.", "created_by": user if user.is_authenticated else None},
    )
    return company


DEFAULT_SYSTEM_MODULES = {
    SystemModuleControl.Module.TASKS: "Task management, Kanban workflows, approvals, and delivery tracking.",
    SystemModuleControl.Module.COLLABORATION: "Realtime channels, team messages, typing signals, and project communication.",
    SystemModuleControl.Module.TICKETS: "Support tickets, screenshots, comments, assignment, and service workflow.",
    SystemModuleControl.Module.NOTIFICATIONS: "Realtime alerts, dashboard badges, broadcast messages, and user notifications.",
    SystemModuleControl.Module.AI_CHATBOT: "AI task suggestions, assistant-ready workflows, and project intelligence.",
    SystemModuleControl.Module.MONITORING: "Operational dashboards, telemetry feeds, and service health indicators.",
    SystemModuleControl.Module.CONNECTION_ENGINE: "Universal connectors, sync events, API bridges, and integration health.",
    SystemModuleControl.Module.PROJECT_FILES: "Document upload, review, visibility control, and file approvals.",
    SystemModuleControl.Module.ANALYTICS: "Portfolio metrics, performance analytics, reports, and executive visibility.",
    SystemModuleControl.Module.AUDIT: "Immutable audit events for settings, API activity, deployments, and governance.",
}

DEFAULT_ADVANCED_FLAGS = [
    ("ai_copilot", "AI Copilot Automation", "GLOBAL", {"tier": "power", "description": "Generate task plans, incident summaries, and project flow recommendations."}),
    ("zero_trust_access", "Zero Trust Access Guard", "GLOBAL", {"tier": "security", "description": "Require least-privilege review for sensitive modules and admin actions."}),
    ("realtime_ops", "Realtime Operations Mesh", "GLOBAL", {"tier": "realtime", "description": "Use WebSocket-ready event fanout for settings, projects, tickets, and notifications."}),
    ("smart_audit", "Smart Audit Intelligence", "SUPER_ADMIN", {"tier": "governance", "description": "Surface risky changes, stale keys, and privileged access drift."}),
    ("auto_backup_policy", "Autonomous Backup Policy", "GLOBAL", {"tier": "resilience", "description": "Keep storage backup posture visible and ready for scheduled automation."}),
    ("developer_power_tools", "Developer Power Tools", "DEVELOPER", {"tier": "engineering", "description": "Expose branch, deployment, API key, and environment controls to approved developers."}),
]


def ensure_settings_defaults(company, user):
    for module, description in DEFAULT_SYSTEM_MODULES.items():
        SystemModuleControl.objects.get_or_create(
            company=company,
            module=module,
            defaults={"description": description, "changed_by": user if user.is_authenticated else None},
        )
    AuthenticationSettings.objects.get_or_create(company=company)
    CloudStorageSettings.objects.get_or_create(company=company)
    for key, label, dashboard, config in DEFAULT_ADVANCED_FLAGS:
        FeatureFlag.objects.get_or_create(
            company=company,
            key=key,
            dashboard=dashboard,
            defaults={"label": label, "is_enabled": True, "config": config},
        )
    ServerControlState.objects.get_or_create(company=company)


class CompanyScopedMixin:
    def filter_company(self, qs):
        user = self.request.user
        company = scoped_company(user)
        if has_role(user, Roles.SUPER_ADMIN) or user.is_superuser:
            return qs
        if company:
            return qs.filter(Q(company=company) | Q(company__isnull=True))
        if is_admin_level(user):
            return qs
        return qs.filter(company__isnull=True)


class CompanyViewSet(viewsets.ModelViewSet):
    serializer_class = CompanySerializer
    permission_classes = [IsAuthenticated]
    queryset = Company.objects.all()

    def get_queryset(self):
        if has_role(self.request.user, Roles.SUPER_ADMIN) or self.request.user.is_superuser:
            return Company.objects.all()
        company = scoped_company(self.request.user)
        return Company.objects.filter(id=company.id) if company else Company.objects.none()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class CompanyServiceViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    serializer_class = CompanyServiceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return self.filter_company(CompanyService.objects.select_related("company"))

    def perform_create(self, serializer):
        serializer.save(company=serializer.validated_data.get("company") or ensure_company(self.request.user))


class UniversalConnectorViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    serializer_class = UniversalConnectorSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = UniversalConnector.objects.select_related("company", "project").annotate(event_count=Count("events"))
        if is_admin_level(self.request.user):
            return self.filter_company(qs)
        if has_role(self.request.user, Roles.DEVELOPER):
            return qs.filter(Q(project__developers=self.request.user) | Q(project__teams__members=self.request.user)).distinct()
        if has_role(self.request.user, Roles.CLIENT):
            return qs.filter(project__client=self.request.user).distinct()
        return qs.none()

    def perform_create(self, serializer):
        connector = serializer.save(company=serializer.validated_data.get("company") or ensure_company(self.request.user))
        ConnectionEvent.objects.create(
            company=connector.company,
            connector=connector,
            project=connector.project,
            actor=self.request.user,
            event_type=ConnectionEvent.EventType.CREATED,
            title=f"{connector.name} connector created",
            payload={"category": connector.category, "vendor": connector.vendor},
        )

    @decorators.action(detail=True, methods=["post"])
    def sync(self, request, pk=None):
        connector = self.get_object()
        if not connector.is_enabled:
            return Response({"detail": "Connector is disabled."}, status=status.HTTP_400_BAD_REQUEST)
        records_in = int(request.data.get("records_in", 12))
        records_out = int(request.data.get("records_out", 8))
        latency_ms = int(request.data.get("latency_ms", max(24, connector.latency_ms or 120)))
        connector.status = UniversalConnector.Status.SYNCING
        connector.save(update_fields=["status", "updated_at"])
        ConnectionEvent.objects.create(
            company=connector.company,
            connector=connector,
            project=connector.project,
            actor=request.user,
            event_type=ConnectionEvent.EventType.SYNC_STARTED,
            title=f"{connector.name} sync started",
            payload={"records_in": records_in, "records_out": records_out},
        )
        connector.mark_synced(records_in=records_in, records_out=records_out, latency_ms=latency_ms)
        ConnectionEvent.objects.create(
            company=connector.company,
            connector=connector,
            project=connector.project,
            actor=request.user,
            event_type=ConnectionEvent.EventType.SYNC_COMPLETED,
            title=f"{connector.name} sync completed",
            payload={"records_in": records_in, "records_out": records_out, "latency_ms": latency_ms},
        )
        return Response(UniversalConnectorSerializer(connector, context={"request": request}).data)

    @decorators.action(detail=True, methods=["post"])
    def control(self, request, pk=None):
        if not is_admin_level(request.user):
            return Response({"detail": "Only Admin and Super Admin can control connectors."}, status=status.HTTP_403_FORBIDDEN)
        connector = self.get_object()
        if "is_enabled" in request.data:
            connector.is_enabled = bool(request.data["is_enabled"])
            connector.status = UniversalConnector.Status.CONNECTED if connector.is_enabled else UniversalConnector.Status.DISCONNECTED
        if "ai_enhancement_enabled" in request.data:
            connector.ai_enhancement_enabled = bool(request.data["ai_enhancement_enabled"])
        connector.save(update_fields=["is_enabled", "status", "ai_enhancement_enabled", "updated_at"])
        ConnectionEvent.objects.create(
            company=connector.company,
            connector=connector,
            project=connector.project,
            actor=request.user,
            event_type=ConnectionEvent.EventType.CONTROL,
            title=f"{connector.name} control updated",
            payload={"is_enabled": connector.is_enabled, "ai_enhancement_enabled": connector.ai_enhancement_enabled},
        )
        return Response(UniversalConnectorSerializer(connector, context={"request": request}).data)


class ConnectionEventViewSet(CompanyScopedMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = ConnectionEventSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = ConnectionEvent.objects.select_related("company", "connector", "project", "actor")
        if is_admin_level(self.request.user):
            return self.filter_company(qs)
        if has_role(self.request.user, Roles.DEVELOPER):
            return qs.filter(Q(project__developers=self.request.user) | Q(project__teams__members=self.request.user)).distinct()
        if has_role(self.request.user, Roles.CLIENT):
            return qs.filter(project__client=self.request.user)
        return qs.none()


class CollaborationChannelViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    serializer_class = CollaborationChannelSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = CollaborationChannel.objects.select_related("company", "project").prefetch_related("members")
        if is_admin_level(self.request.user):
            return self.filter_company(qs)
        return qs.filter(Q(members=self.request.user) | Q(project__developers=self.request.user) | Q(project__teams__members=self.request.user)).distinct()

    def perform_create(self, serializer):
        project = serializer.validated_data.get("project")
        channel = serializer.save(company=serializer.validated_data.get("company") or getattr(project, "company", None) or ensure_company(self.request.user))
        channel.members.add(self.request.user)
        if project:
            channel.members.add(*project.developers.all(), *project.admins.all())
            if project.owner:
                channel.members.add(project.owner)

    @decorators.action(detail=True, methods=["get", "post"])
    def messages(self, request, pk=None):
        channel = self.get_object()
        if request.method == "GET":
            messages = channel.messages.select_related("sender")[:100]
            return Response(CollaborationMessageSerializer(messages, many=True, context={"request": request}).data)
        serializer = CollaborationMessageSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        message = serializer.save(sender=request.user, channel=channel, attachment_name=getattr(serializer.validated_data.get("attachment"), "name", ""))
        self._broadcast_message(channel, message)
        created = [message]
        if message.kind == CollaborationMessage.Kind.MESSAGE and "bot" in message.metadata.get("mentions", []):
            bot = CollaborationMessage.objects.create(
                channel=channel,
                sender=None,
                kind=CollaborationMessage.Kind.BOT,
                ciphertext="TeamBot: Check project docs, environment variables, deployment controls, and blockers before pushing changes.",
                metadata={"bot": "internal_team_chatbot", "encrypted": False},
            )
            self._broadcast_message(channel, bot)
            created.append(bot)
        return Response(CollaborationMessageSerializer(created, many=True, context={"request": request}).data, status=status.HTTP_201_CREATED)

    @decorators.action(detail=True, methods=["post"])
    def typing(self, request, pk=None):
        channel = self.get_object()
        channel_layer = get_channel_layer()
        if channel_layer:
            for member in channel.members.all():
                if member.id != request.user.id:
                    async_to_sync(channel_layer.group_send)(
                        f"user_{member.id}",
                        {
                            "type": "collaboration.typing",
                            "typing": {"channel": channel.id, "user": request.user.email, "is_typing": bool(request.data.get("is_typing", True))},
                        },
                    )
        return Response({"ok": True})

    def _broadcast_message(self, channel, message):
        channel_layer = get_channel_layer()
        if not channel_layer:
            return
        payload = CollaborationMessageSerializer(message, context={"request": self.request}).data
        for member in channel.members.all():
            try:
                async_to_sync(channel_layer.group_send)(f"user_{member.id}", {"type": "collaboration.message", "message": payload})
            except Exception:
                pass


class FeatureFlagViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    serializer_class = FeatureFlagSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return self.filter_company(FeatureFlag.objects.select_related("company"))

    def check_admin(self):
        if not is_admin_level(self.request.user):
            return Response({"detail": "Only Admin and Super Admin can change feature settings."}, status=status.HTTP_403_FORBIDDEN)
        return None

    def create(self, request, *args, **kwargs):
        blocked = self.check_admin()
        return blocked or super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        blocked = self.check_admin()
        return blocked or super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        blocked = self.check_admin()
        return blocked or super().partial_update(request, *args, **kwargs)


class APIKeyViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    serializer_class = APIKeySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = APIKey.objects.select_related("company", "created_by").prefetch_related("grants", "grants__developer")
        if is_admin_level(self.request.user):
            return self.filter_company(qs)
        return qs.filter(grants__developer=self.request.user, grants__can_view=True, is_active=True).distinct()

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "request": self.request}

    def create(self, request, *args, **kwargs):
        if not is_admin_level(request.user):
            return Response({"detail": "Only Admin and Super Admin can add API keys."}, status=status.HTTP_403_FORBIDDEN)
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if not is_admin_level(request.user):
            return Response({"detail": "Only Admin and Super Admin can update API keys."}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)


class APIKeyGrantViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    serializer_class = APIKeyGrantSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = APIKeyGrant.objects.select_related("api_key", "developer", "granted_by", "api_key__company")
        if is_admin_level(self.request.user):
            return self.filter_company(qs)
        return qs.filter(developer=self.request.user, can_view=True)

    def perform_create(self, serializer):
        serializer.save(granted_by=self.request.user)


class ProjectEstimateViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    serializer_class = ProjectEstimateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = ProjectEstimate.objects.select_related("company", "project", "client", "created_by")
        if is_admin_level(self.request.user):
            return self.filter_company(qs)
        return qs.filter(client=self.request.user)

    def perform_create(self, serializer):
        estimate = serializer.save(created_by=self.request.user)
        if estimate.status in {ProjectEstimate.Status.SENT, ProjectEstimate.Status.REQUESTED}:
            self._send_estimate(estimate)

    @decorators.action(detail=True, methods=["post"])
    def send(self, request, pk=None):
        if not is_admin_level(request.user):
            return Response({"detail": "Only Admin and Super Admin can send estimates."}, status=status.HTTP_403_FORBIDDEN)
        estimate = self.get_object()
        self._send_estimate(estimate)
        return Response(ProjectEstimateSerializer(estimate, context={"request": request}).data)

    def _send_estimate(self, estimate):
        estimate.mark_sent()
        body = (
            f"Project estimation: {estimate.title}\n\n"
            f"Scope: {estimate.scope}\n"
            f"Timeline: {estimate.timeline_days} days\n"
            f"Development: {estimate.currency} {estimate.development_cost}\n"
            f"Hosting: {estimate.currency} {estimate.hosting_cost}\n"
            f"Maintenance: {estimate.currency} {estimate.maintenance_cost}\n"
            f"Total: {estimate.currency} {estimate.total_cost}"
            f"\nDemo preview: {estimate.demo_url or 'Not attached'}"
        )
        send_automation_email(estimate.client.email, f"Project estimation - {estimate.title}", body, company=estimate.company)
        notify_user(
            recipient=estimate.client,
            sender=self.request.user,
            title="Project estimation ready",
            message=f"{estimate.title} estimate is ready. Total: {estimate.currency} {estimate.total_cost}.",
            type="INFO",
            project=estimate.project,
        )


class EmailEventViewSet(CompanyScopedMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = EmailEventSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if not is_admin_level(self.request.user):
            return EmailEvent.objects.none()
        return self.filter_company(EmailEvent.objects.select_related("company"))


class HostingConnectionViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    serializer_class = HostingConnectionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = HostingConnection.objects.select_related("company", "project")
        if is_admin_level(self.request.user):
            return self.filter_company(qs)
        if has_role(self.request.user, Roles.DEVELOPER):
            return qs.filter(project__developers=self.request.user).distinct()
        if has_role(self.request.user, Roles.CLIENT):
            return qs.filter(project__client=self.request.user).distinct()
        return qs.none()

    @decorators.action(detail=True, methods=["post"])
    def toggle(self, request, pk=None):
        if not is_admin_level(request.user):
            return Response({"detail": "Only Admin and Super Admin can control hosting."}, status=status.HTTP_403_FORBIDDEN)
        connection = self.get_object()
        connection.is_enabled = bool(request.data.get("is_enabled", not connection.is_enabled))
        connection.status = HostingConnection.Status.CONNECTED if connection.is_enabled else HostingConnection.Status.DISCONNECTED
        connection.last_deployed_at = timezone.now() if connection.is_enabled else connection.last_deployed_at
        connection.save(update_fields=["is_enabled", "status", "last_deployed_at", "updated_at"])
        return Response(HostingConnectionSerializer(connection, context={"request": request}).data)


class ServerControlViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    serializer_class = ServerControlStateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = ServerControlState.objects.select_related("company")
        if is_admin_level(self.request.user):
            return self.filter_company(qs)
        return qs.none()

    @decorators.action(detail=True, methods=["post"])
    def control(self, request, pk=None):
        if not is_admin_level(request.user):
            return Response({"detail": "Only Admin and Super Admin can control server state."}, status=status.HTTP_403_FORBIDDEN)
        server = self.get_object()
        if "is_enabled" in request.data:
            server.is_enabled = bool(request.data["is_enabled"])
        if "scale_units" in request.data:
            server.scale_units = max(1, min(12, int(request.data["scale_units"])))
        server.rotate_live_metrics()
        return Response(ServerControlStateSerializer(server, context={"request": request}).data)

    @decorators.action(detail=False, methods=["get"])
    def live(self, request):
        qs = self.get_queryset()
        server = qs.first()
        if not server:
            company = scoped_company(request.user)
            server = ServerControlState.objects.create(company=company)
        server.rotate_live_metrics()
        return Response(ServerControlStateSerializer(server, context={"request": request}).data)


class NetworkTelemetryViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    serializer_class = NetworkTelemetrySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = NetworkTelemetry.objects.select_related("company")
        if is_admin_level(self.request.user):
            return self.filter_company(qs)
        return self.filter_company(qs)

    def perform_create(self, serializer):
        serializer.save(company=serializer.validated_data.get("company") or ensure_company(self.request.user))

    @decorators.action(detail=False, methods=["get"])
    def live(self, request):
        company = scoped_company(request.user) or ensure_company(request.user)
        latest = NetworkTelemetry.objects.filter(company=company).first()
        seed = timezone.now().second
        item = NetworkTelemetry.objects.create(
            company=company,
            upload_mbps=round(22 + seed * 0.9, 2),
            download_mbps=round(120 + seed * 1.7, 2),
            latency_ms=18 + seed % 36,
            packet_loss_percent=round((seed % 4) * 0.03, 2),
            requests_per_second=round(42 + seed * 1.35, 2),
            health_score=max(80, 100 - (seed % 18)),
            source=latest.source if latest else "platform-agent",
        )
        history = NetworkTelemetry.objects.filter(company=company)[:24]
        return Response({
            "current": NetworkTelemetrySerializer(item, context={"request": request}).data,
            "history": NetworkTelemetrySerializer(history, many=True, context={"request": request}).data,
        })


class VoiceCommandIntentViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    serializer_class = VoiceCommandIntentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return self.filter_company(VoiceCommandIntent.objects.select_related("company"))

    def perform_create(self, serializer):
        serializer.save(company=serializer.validated_data.get("company") or ensure_company(self.request.user))


class ConnectionEngineSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = scoped_company(request.user)
        connectors = UniversalConnector.objects.all()
        events = ConnectionEvent.objects.select_related("connector", "project", "actor")
        network = NetworkTelemetry.objects.all()
        if company and not has_role(request.user, Roles.SUPER_ADMIN):
            connectors = connectors.filter(Q(company=company) | Q(company__isnull=True))
            events = events.filter(Q(company=company) | Q(company__isnull=True))
            network = network.filter(Q(company=company) | Q(company__isnull=True))
        elif not is_admin_level(request.user):
            connectors = connectors.filter(Q(project__client=request.user) | Q(project__developers=request.user) | Q(project__teams__members=request.user)).distinct()
            events = events.filter(connector__in=connectors)

        by_category = connectors.values("category").annotate(total=Count("id")).order_by("category")
        latest_network = network.first()
        return Response({
            "totals": {
                "connectors": connectors.count(),
                "connected": connectors.filter(status=UniversalConnector.Status.CONNECTED, is_enabled=True).count(),
                "syncing": connectors.filter(status=UniversalConnector.Status.SYNCING).count(),
                "degraded": connectors.filter(status=UniversalConnector.Status.DEGRADED).count(),
                "events": events.count(),
            },
            "by_category": list(by_category),
            "latest_network": NetworkTelemetrySerializer(latest_network, context={"request": request}).data if latest_network else None,
            "recent_events": ConnectionEventSerializer(events[:10], many=True, context={"request": request}).data,
        })


class ReportExportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, kind):
        fmt = request.query_params.get("format", "pdf").lower()
        title, rows, table = self._report_payload(request.user, kind)
        if fmt in {"xlsx", "excel"}:
            content = make_xlsx(["Metric", "Value"], table)
            response = HttpResponse(content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response["Content-Disposition"] = f'attachment; filename="{kind}-report.xlsx"'
            return response
        content = make_pdf(title, rows)
        response = HttpResponse(content, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{kind}-report.pdf"'
        return response

    def _visible_projects(self, user):
        qs = Project.objects.all()
        company = scoped_company(user)
        if company:
            qs = qs.filter(Q(company=company) | Q(company__isnull=True))
        if has_role(user, Roles.SUPER_ADMIN):
            return qs
        if has_role(user, Roles.ADMIN):
            return qs.filter(Q(owner=user) | Q(admins=user) | Q(created_by=user)).distinct()
        if has_role(user, Roles.DEVELOPER):
            return qs.filter(Q(developers=user) | Q(teams__members=user)).distinct()
        if has_role(user, Roles.CLIENT):
            return qs.filter(client=user)
        return qs.none()

    def _report_payload(self, user, kind):
        projects = self._visible_projects(user)
        tasks = Task.objects.filter(project__in=projects)
        tickets = Ticket.objects.filter(project__in=projects)
        documents = Document.objects.filter(project__in=projects)
        deployments = DeploymentControl.objects.filter(project__in=projects)
        estimates = ProjectEstimate.objects.filter(Q(project__in=projects) | Q(client=user)).distinct()

        if kind == "client":
            price_parts = estimates.aggregate(development=Sum("development_cost"), hosting=Sum("hosting_cost"), maintenance=Sum("maintenance_cost"))
            total_price = (price_parts["development"] or Decimal("0")) + (price_parts["hosting"] or Decimal("0")) + (price_parts["maintenance"] or Decimal("0"))
            rows = [
                ("Client", user.get_full_name() or user.email),
                ("Projects", projects.count()),
                ("Average progress", f"{round(sum(project.progress for project in projects) / max(projects.count(), 1), 2)}%"),
                ("Open tickets", tickets.exclude(status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED]).count()),
                ("Approved documents", documents.filter(review_status=Document.ReviewStatus.APPROVED).count()),
                ("Estimated price", total_price),
            ]
            return "Client Project Report", rows, rows

        if kind == "developer":
            developers = User.objects.filter(role=Roles.DEVELOPER)
            if not is_admin_level(user):
                developers = developers.filter(id=user.id)
            completed_tasks = tasks.filter(status=Task.Status.DONE)
            rows = [
                ("Developers", developers.count()),
                ("Completed tasks", completed_tasks.count()),
                ("Completed projects", projects.filter(progress=100).count()),
                ("Blocked tasks", tasks.filter(status=Task.Status.BLOCKED).count()),
                ("Productivity score", max(0, min(100, completed_tasks.count() * 8 - tasks.filter(status=Task.Status.BLOCKED).count() * 5))),
                ("Rating", "4.8/5" if completed_tasks.exists() else "Pending"),
            ]
            return "Developer Performance Report", rows, rows

        if not is_admin_level(user):
            rows = [("Access", "Admin report requires Admin or Super Admin access")]
            return "Admin System Report", rows, rows
        rows = [
            ("Projects", projects.count()),
            ("Users", User.objects.count()),
            ("Tasks", tasks.count()),
            ("Tickets", tickets.count()),
            ("Documents", documents.count()),
            ("Deployments ON", deployments.filter(is_enabled=True).count()),
            ("API keys", APIKey.objects.count()),
            ("Email events", EmailEvent.objects.count()),
            ("Hosting connections", HostingConnection.objects.count()),
        ]
        return "Admin Database Insights Report", rows, rows


# ==================== SETTINGS MODULE ====================


class SystemModuleControlViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """Control enable/disable of system modules"""

    serializer_class = SystemModuleControlSerializer
    permission_classes = [IsAuthenticated, IsAdminLevel]

    def get_queryset(self):
        qs = SystemModuleControl.objects.select_related("company", "changed_by")
        return self.filter_company(qs)

    def perform_create(self, serializer):
        serializer.save(company=serializer.validated_data.get("company") or ensure_company(self.request.user), changed_by=self.request.user)

    def perform_update(self, serializer):
        old_values = {
            "is_enabled": serializer.instance.is_enabled,
        }
        instance = serializer.save(changed_by=self.request.user)
        self._audit_log("UPDATE", instance, old_values, {"is_enabled": instance.is_enabled})
        self._broadcast_settings_change(instance)

    def _audit_log(self, action, instance, old_values, new_values):
        SystemSettingsAuditLog.objects.create(
            company=instance.company,
            changed_by=self.request.user,
            entity_type=SystemSettingsAuditLog.EntityType.MODULE_CONTROL,
            entity_id=instance.id,
            action=action,
            old_values=old_values,
            new_values=new_values,
            change_summary=f"{instance.module} changed to {'Enabled' if new_values.get('is_enabled') else 'Disabled'}",
        )

    def _broadcast_settings_change(self, instance):
        channel_layer = get_channel_layer()
        if not channel_layer:
            return
        try:
            async_to_sync(channel_layer.group_send)("settings_updates", {
                "type": "settings.module_changed",
                "module": instance.module,
                "is_enabled": instance.is_enabled,
            })
        except Exception:
            pass


class UserAccessControlViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """Manage role-based access control per user and module"""

    serializer_class = UserAccessControlSerializer
    permission_classes = [IsAuthenticated, IsAdminLevel]

    def get_queryset(self):
        qs = UserAccessControl.objects.select_related("company", "user", "granted_by")
        return self.filter_company(qs)

    def perform_create(self, serializer):
        serializer.save(company=serializer.validated_data.get("company") or ensure_company(self.request.user), granted_by=self.request.user)

    def perform_update(self, serializer):
        old_instance = UserAccessControl.objects.get(pk=serializer.instance.id)
        old_values = {
            "actions": old_instance.actions,
            "is_enabled": old_instance.is_enabled,
        }
        instance = serializer.save()
        SystemSettingsAuditLog.objects.create(
            company=instance.company,
            changed_by=self.request.user,
            entity_type=SystemSettingsAuditLog.EntityType.ACCESS_CONTROL,
            entity_id=instance.id,
            action="UPDATE",
            old_values=old_values,
            new_values={"actions": instance.actions, "is_enabled": instance.is_enabled},
            change_summary=f"Access for {instance.user.email} on {instance.module} updated",
        )


class AuthenticationSettingsViewSet(viewsets.ModelViewSet):
    """Manage company authentication settings"""

    serializer_class = AuthenticationSettingsSerializer
    permission_classes = [IsAuthenticated, IsAdminLevel]

    def get_queryset(self):
        company = ensure_company(self.request.user)
        ensure_settings_defaults(company, self.request.user)
        return AuthenticationSettings.objects.filter(company=company)

    def perform_update(self, serializer):
        old_instance = AuthenticationSettings.objects.get(pk=serializer.instance.id)
        old_values = {
            "allow_password_change": old_instance.allow_password_change,
            "allow_forgot_password": old_instance.allow_forgot_password,
        }
        instance = serializer.save(updated_by=self.request.user)
        SystemSettingsAuditLog.objects.create(
            company=instance.company,
            changed_by=self.request.user,
            entity_type=SystemSettingsAuditLog.EntityType.AUTH_SETTINGS,
            entity_id=instance.id,
            action="UPDATE",
            old_values=old_values,
            new_values={"allow_password_change": instance.allow_password_change, "allow_forgot_password": instance.allow_forgot_password},
            change_summary="Authentication settings updated",
        )
        self._broadcast_settings_change(instance)

    def _broadcast_settings_change(self, instance):
        channel_layer = get_channel_layer()
        if not channel_layer:
            return
        try:
            async_to_sync(channel_layer.group_send)("settings_updates", {
                "type": "settings.auth_changed",
                "company_id": instance.company_id,
            })
        except Exception:
            pass


class CloudStorageSettingsViewSet(viewsets.ModelViewSet):
    """Manage cloud storage settings"""

    serializer_class = CloudStorageSettingsSerializer
    permission_classes = [IsAuthenticated, IsAdminLevel]

    def get_queryset(self):
        company = ensure_company(self.request.user)
        ensure_settings_defaults(company, self.request.user)
        return CloudStorageSettings.objects.filter(company=company)

    def perform_update(self, serializer):
        old_instance = CloudStorageSettings.objects.get(pk=serializer.instance.id)
        old_values = {
            "provider": old_instance.provider,
            "is_enabled": old_instance.is_enabled,
        }
        instance = serializer.save(updated_by=self.request.user)
        SystemSettingsAuditLog.objects.create(
            company=instance.company,
            changed_by=self.request.user,
            entity_type=SystemSettingsAuditLog.EntityType.STORAGE_SETTINGS,
            entity_id=instance.id,
            action="UPDATE",
            old_values=old_values,
            new_values={"provider": instance.provider, "is_enabled": instance.is_enabled},
            change_summary=f"Storage changed to {instance.provider}",
        )


class ServerFileAccessViewSet(CompanyScopedMixin, viewsets.ReadOnlyModelViewSet):
    """View audit log of server file access"""

    serializer_class = ServerFileAccessSerializer
    permission_classes = [IsAuthenticated, IsAdminLevel]

    def get_queryset(self):
        qs = ServerFileAccess.objects.select_related("company", "accessed_by").order_by("-created_at")
        return self.filter_company(qs)

    @decorators.action(detail=False, methods=["post"])
    def log_access(self, request):
        """Log a file access event"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(accessed_by=request.user, company=request.user.company)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class SystemSettingsAuditLogViewSet(CompanyScopedMixin, viewsets.ReadOnlyModelViewSet):
    """View settings audit logs"""

    serializer_class = SystemSettingsAuditLogSerializer
    permission_classes = [IsAuthenticated, IsAdminLevel]

    def get_queryset(self):
        qs = SystemSettingsAuditLog.objects.select_related("company", "changed_by").order_by("-created_at")
        return self.filter_company(qs)


class SettingsDashboardView(APIView):
    """Get comprehensive settings dashboard data"""

    permission_classes = [IsAuthenticated, IsAdminLevel]

    def get(self, request):
        company = scoped_company(request.user)
        if not company:
            company = ensure_company(request.user)
        ensure_settings_defaults(company, request.user)

        modules = SystemModuleControl.objects.filter(company=company)
        access_controls = UserAccessControl.objects.filter(company=company).select_related("user")
        auth_settings = AuthenticationSettings.objects.filter(company=company).first()
        storage_settings = CloudStorageSettings.objects.filter(company=company).first()
        audit_logs = SystemSettingsAuditLog.objects.filter(company=company).order_by("-created_at")[:20]
        advanced_features = FeatureFlag.objects.filter(company=company).order_by("dashboard", "label")
        server_control = ServerControlState.objects.filter(company=company).first()
        connectors = UniversalConnector.objects.filter(company=company)

        return Response({
            "modules": SystemModuleControlSerializer(modules, many=True, context={"request": request}).data,
            "access_controls": UserAccessControlSerializer(access_controls, many=True, context={"request": request}).data,
            "auth_settings": AuthenticationSettingsSerializer(auth_settings, context={"request": request}).data if auth_settings else None,
            "storage_settings": CloudStorageSettingsSerializer(storage_settings, context={"request": request}).data if storage_settings else None,
            "advanced_features": FeatureFlagSerializer(advanced_features, many=True, context={"request": request}).data,
            "server_control": ServerControlStateSerializer(server_control, context={"request": request}).data if server_control else None,
            "settings_health": {
                "enabled_modules": modules.filter(is_enabled=True).count(),
                "total_modules": modules.count(),
                "advanced_features": advanced_features.filter(is_enabled=True).count(),
                "connectors": connectors.count(),
                "active_connectors": connectors.filter(is_enabled=True).count(),
                "storage_usage_percent": storage_settings.usage_percent if storage_settings else 0,
                "zero_trust_enabled": advanced_features.filter(key="zero_trust_access", is_enabled=True).exists(),
            },
            "recent_audit_logs": SystemSettingsAuditLogSerializer(audit_logs, many=True, context={"request": request}).data,
        })
