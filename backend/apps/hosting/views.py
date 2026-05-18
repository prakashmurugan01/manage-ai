from datetime import timedelta
import csv
import time

from django.core.cache import cache
from django.db.models import Avg, Count, Sum
from django.db.models.functions import TruncMonth
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.api_keys.utils import _fernet
from apps.audit.services import audit_event

from .models import DeploymentRun, DomainStatus, EmailAccount, HostedProject, HostingApiUsageLog, HostingLifecycle, HostingProjectApiKey, HostingLink, HostingProvider, HostingStatus, ProjectUpload, VercelDeployment, VercelProject
from .netlify import NetlifyApiError, NetlifyClient, get_netlify_status
from .providers import ProviderError, evaluate_failover, failover_all_projects, sync_all_providers, toggle_hosting_link
from .services import ProviderConnectionError, get_service
from .serializers import (
    HostedProjectSerializer,
    DeploymentRunSerializer,
    DomainStatusSerializer,
    EmailAccountSerializer,
    HostingFailoverStateSerializer,
    HostingApiUsageLogSerializer,
    HostingLifecycleSerializer,
    HostingLinkSerializer,
    HostingProviderSerializer,
    HostingProjectApiKeySerializer,
    HostingStatusSerializer,
    ProjectUploadSerializer,
    VercelDeploymentSerializer,
    VercelProjectSerializer,
)
from .vercel import VercelApiError, VercelClient, set_vercel_access, sync_project_deployments, sync_vercel_projects


class NetlifyStatusView(APIView):
    def get(self, request):
        try:
            payload = get_netlify_status(force=request.query_params.get("fresh") == "1")
            HostingProvider.objects.filter(provider=HostingProvider.Provider.NETLIFY).update(last_error="", last_synced_at=timezone.now())
            return Response(payload)
        except NetlifyApiError as exc:
            HostingProvider.objects.filter(provider=HostingProvider.Provider.NETLIFY).update(last_error=str(exc))
            return Response(
                {
                    "active": 0,
                    "failed": 0,
                    "uptime": "0%",
                    "uptimeValue": 0,
                    "lastDeploy": "",
                    "lastDeployLabel": "Unavailable",
                    "status": "Error",
                    "indicator": "Error",
                    "sites": [],
                    "deploys": [],
                    "logsPreview": [{"level": "error", "title": "Netlify API", "message": str(exc)}],
                    "detail": str(exc),
                    "payload": exc.payload,
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )


class NetlifyRedeployView(APIView):
    def post(self, request):
        site_id = request.data.get("site_id") or request.data.get("siteId")
        if not site_id:
            try:
                payload = get_netlify_status(force=False)
            except NetlifyApiError as exc:
                return Response({"detail": str(exc), "payload": exc.payload}, status=exc.status_code or status.HTTP_502_BAD_GATEWAY)
            site_id = (payload.get("sites") or [{}])[0].get("id")
        if not site_id:
            return Response({"detail": "site_id is required when no Netlify sites are available."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = NetlifyClient().trigger_build(site_id)
        except NetlifyApiError as exc:
            return Response({"detail": str(exc), "payload": exc.payload}, status=exc.status_code or status.HTTP_502_BAD_GATEWAY)
        audit_event(request, "hosting.netlify_redeploy", "NetlifySite", metadata={"site_id": site_id})
        return Response({"detail": "Netlify redeploy requested.", "site_id": site_id, "payload": result})


class UnifiedHostingProviderView(APIView):
    def get(self, request, provider, project_id=None, operation=None):
        try:
            service = get_service(provider, user=request.user)
            if operation == "status" and project_id:
                payload = service.get_status(project_id)
                return _provider_success_response(payload, _status_value(payload))
            if operation == "logs" and project_id:
                return _provider_success_response({"logs": service.fetch_logs(project_id)}, "running")
            if project_id:
                payload = service.get_project_details(project_id)
                return _provider_success_response(payload, _status_value(payload.get("status")))
            return _provider_success_response({"provider": provider, "projects": service.get_projects()}, "running")
        except ProviderConnectionError as exc:
            return _provider_error_response(exc)

    def post(self, request, provider, project_id=None, operation=None):
        try:
            service = get_service(provider, user=request.user)
            if operation == "start":
                payload = service.start_server(project_id)
            elif operation == "stop":
                payload = service.stop_server(project_id)
            elif operation == "restart":
                payload = service.restart_server(project_id)
            elif operation == "redeploy":
                payload = service.redeploy(project_id)
            elif operation == "sync":
                payload = {"provider": provider, "projects": service.get_projects()}
            else:
                return Response({"detail": "Unsupported provider operation."}, status=status.HTTP_404_NOT_FOUND)
            audit_event(request, f"hosting.{provider}.{operation}", "HostingProvider", metadata={"project_id": project_id})
            payload_status = _status_value((payload.get("project") or {}).get("status")) if isinstance(payload, dict) else "running"
            return _provider_success_response(payload, payload_status)
        except ProviderConnectionError as exc:
            return _provider_error_response(exc)


class HostedProjectViewSet(viewsets.ModelViewSet):
    queryset = HostedProject.objects.select_related("client").prefetch_related("lifecycle", "api_keys")
    serializer_class = HostedProjectSerializer
    search_fields = ["name", "domain", "client__name", "client_name", "deploy_url", "server_ip"]
    filterset_fields = ["status", "tag", "server_status", "hosting_platform", "link_is_active"]
    ordering_fields = ["expiry_date", "name", "created_at", "monthly_cost"]

    def get_queryset(self):
        queryset = super().get_queryset()
        tag = self.request.query_params.get("tag")
        if tag == "expiring":
            today = timezone.localdate()
            return queryset.filter(expiry_date__gte=today, expiry_date__lte=today + timedelta(days=60))
        if tag == "expired":
            return queryset.filter(expiry_date__lt=timezone.localdate())
        if tag == "maintenance":
            return queryset.filter(status=HostedProject.Status.MAINTENANCE)
        if tag == "active":
            return queryset.filter(status=HostedProject.Status.LIVE, link_is_active=True)
        if tag == "archived":
            return queryset.filter(archived_at__isnull=False)
        return queryset

    def perform_create(self, serializer):
        obj = serializer.save()
        audit_event(self.request, "hosting.created", "HostedProject", obj.id, {"domain": obj.domain})

    def perform_update(self, serializer):
        obj = serializer.save()
        audit_event(self.request, "hosting.updated", "HostedProject", obj.id, {"domain": obj.domain})

    def perform_destroy(self, instance):
        audit_event(self.request, "hosting.deleted", "HostedProject", instance.id, {"domain": instance.domain})
        return super().perform_destroy(instance)

    @action(detail=True, methods=["post"])
    def renew(self, request, pk=None):
        project = self.get_object()
        new_expiry = request.data.get("new_expiry") or request.data.get("expiry_date")
        if not new_expiry:
            return Response({"detail": "new_expiry is required."}, status=status.HTTP_400_BAD_REQUEST)
        old_expiry = project.expiry_date
        old_platform = project.hosting_platform
        new_platform = request.data.get("hosting_platform") or old_platform
        project.expiry_date = new_expiry
        project.hosting_platform = new_platform
        project.status = HostedProject.Status.LIVE
        project.tag = "active"
        project.archived_at = None
        project.save(update_fields=["expiry_date", "hosting_platform", "status", "tag", "archived_at"])
        HostingLifecycle.objects.create(
            project=project,
            event_type=HostingLifecycle.Event.RENEWED if old_platform == new_platform else HostingLifecycle.Event.PLATFORM_CHANGED,
            old_expiry=old_expiry,
            new_expiry=project.expiry_date,
            old_platform=old_platform,
            new_platform=new_platform,
            performed_by=request.user if request.user.is_authenticated else None,
            notes=request.data.get("notes", ""),
        )
        audit_event(request, "hosting.renewed", "HostedProject", project.id, {"old_expiry": str(old_expiry), "new_expiry": str(project.expiry_date)})
        return Response(self.get_serializer(project).data)

    @action(detail=True, methods=["post", "patch"])
    def toggle_link(self, request, pk=None):
        project = self.get_object()
        force_state = request.data.get("link_is_active")
        if isinstance(force_state, str):
            force_state = force_state.lower() in {"1", "true", "yes", "on"}
        project.link_is_active = (not project.link_is_active) if force_state is None else bool(force_state)
        project.save(update_fields=["link_is_active"])
        audit_event(request, "hosting.link_toggled", "HostedProject", project.id, {"link_is_active": project.link_is_active})
        return Response(self.get_serializer(project).data)

    @action(detail=True, methods=["post"], url_path="health-check")
    def health_check(self, request, pk=None):
        from .tasks import check_hosted_project_health

        project = self.get_object()
        check_hosted_project_health.delay(project.id)
        return Response({"detail": "Health check queued."})

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        project = self.get_object()
        project.archived_at = timezone.now()
        project.status = HostedProject.Status.EXPIRED
        project.tag = "expired"
        project.link_is_active = False
        project.save(update_fields=["archived_at", "status", "tag", "link_is_active"])
        HostingLifecycle.objects.create(project=project, event_type=HostingLifecycle.Event.ARCHIVED, performed_by=request.user, notes=request.data.get("notes", "Archived from Hosting Manager"))
        audit_event(request, "hosting.archived", "HostedProject", project.id, {"domain": project.domain})
        return Response(self.get_serializer(project).data)

    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        project = self.get_object()
        project.archived_at = None
        project.status = HostedProject.Status.LIVE
        project.tag = "active"
        project.link_is_active = True
        project.save(update_fields=["archived_at", "status", "tag", "link_is_active"])
        HostingLifecycle.objects.create(project=project, event_type=HostingLifecycle.Event.RESTORED, performed_by=request.user, notes=request.data.get("notes", "Restored from archive"))
        audit_event(request, "hosting.restored", "HostedProject", project.id, {"domain": project.domain})
        return Response(self.get_serializer(project).data)

    @action(detail=True, methods=["get"])
    def timeline(self, request, pk=None):
        project = self.get_object()
        return Response(HostingLifecycleSerializer(project.lifecycle.all(), many=True).data)

    @action(detail=False, methods=["get"])
    def summary(self, request):
        queryset = self.get_queryset()
        today = timezone.localdate()
        total = queryset.count()
        down = queryset.filter(server_status=HostedProject.ServerStatus.OFFLINE).count()
        slow = queryset.filter(server_status=HostedProject.ServerStatus.SLOW).count()
        online = queryset.filter(server_status=HostedProject.ServerStatus.ONLINE).count()
        expiring = queryset.filter(expiry_date__gte=today, expiry_date__lte=today + timedelta(days=60)).count()
        revenue = queryset.aggregate(monthly=Sum("monthly_cost"))["monthly"] or 0
        uptime_avg = queryset.aggregate(avg=Avg("uptime_percentage"))["avg"] or 0
        return Response(
            {
                "total_projects": total,
                "active_servers": online,
                "slow_servers": slow,
                "down_servers": down,
                "expiring_soon": expiring,
                "link_active": queryset.filter(link_is_active=True).count(),
                "monthly_revenue": revenue,
                "average_uptime": round(float(uptime_avg), 2),
                "archived_projects": queryset.filter(archived_at__isnull=False).count(),
            }
        )

    @action(detail=False, methods=["get"])
    def dashboard(self, request):
        queryset = self.get_queryset()
        today = timezone.localdate()
        expiry_trends = (
            queryset.annotate(month=TruncMonth("expiry_date"))
            .values("month")
            .annotate(count=Count("id"))
            .order_by("month")[:12]
        )
        uptime = queryset.order_by("-last_checked_at").values("id", "name", "domain", "server_status", "uptime_percentage", "response_time_ms", "last_checked_at")[:20]
        insights = []
        for project in queryset.order_by("expiry_date")[:20]:
            days = (project.expiry_date - today).days
            if project.downtime_count >= 3 or float(project.uptime_percentage or 100) < 95:
                insights.append({"project": project.name, "type": "failure_risk", "message": "High failure risk: unstable uptime or repeated downtime."})
            if 0 <= days <= 30:
                insights.append({"project": project.name, "type": "renewal", "message": f"Renew within {days} day(s) to avoid service interruption."})
        return Response({"summary": self.summary(request).data, "expiry_trends": list(expiry_trends), "uptime": list(uptime), "ai_insights": insights[:10]})

    @action(detail=False, methods=["get"], url_path="universal-overview")
    def universal_overview(self, request):
        providers = HostingProvider.objects.prefetch_related("links")
        links = HostingLink.objects.select_related("project", "provider_config")
        email_accounts = EmailAccount.objects.select_related("project")
        domains = DomainStatus.objects.select_related("project")
        return Response(
            {
                "providers": HostingProviderSerializer(providers, many=True).data,
                "links": HostingLinkSerializer(links.order_by("priority", "provider")[:200], many=True).data,
                "email_accounts": EmailAccountSerializer(email_accounts.order_by("project__name", "email")[:200], many=True).data,
                "domains": DomainStatusSerializer(domains.order_by("domain")[:200], many=True).data,
                "summary": {
                    "provider_count": providers.count(),
                    "hosting_link_count": links.count(),
                    "active_link_count": links.filter(is_active=True).count(),
                    "email_account_count": email_accounts.count(),
                    "email_issue_count": email_accounts.exclude(mx_status__in=["healthy", "unknown"]).count(),
                    "domain_issue_count": domains.exclude(mx_status="healthy").count() + domains.exclude(ssl_status="healthy").count(),
                },
            }
        )

    @action(detail=False, methods=["get"], url_path="export")
    def export_report(self, request):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="hosting-report.csv"'
        writer = csv.writer(response)
        writer.writerow(["Client", "Project", "Domain", "Platform", "Status", "Server", "Uptime", "Expiry", "Monthly Cost", "Archived"])
        for project in self.get_queryset():
            writer.writerow([
                project.display_client_name,
                project.name,
                project.domain,
                project.hosting_platform,
                project.status,
                project.server_status,
                project.uptime_percentage,
                project.expiry_date,
                project.monthly_cost,
                project.archived_at or "",
            ])
        audit_event(request, "hosting.exported", "HostedProject", metadata={"format": "csv"})
        return response

    @action(detail=False, methods=["get"], url_path="external-status", permission_classes=[AllowAny])
    def external_status(self, request):
        started = time.perf_counter()
        api_key, error = _validate_hosting_api_key(request)
        if error:
            return Response(error, status=error.get("status", status.HTTP_401_UNAUTHORIZED))
        project = api_key.project
        payload = {
            "project": project.name,
            "domain": project.domain,
            "active_hosting_link": HostingLinkSerializer(project.failover_state.active_link).data if hasattr(project, "failover_state") and project.failover_state.active_link else None,
            "hosting_links": HostingLinkSerializer(project.hosting_links.order_by("priority"), many=True).data,
            "platform": project.hosting_platform,
            "status": project.status,
            "server_status": project.server_status,
            "link_is_active": project.link_is_active,
            "uptime_percentage": project.uptime_percentage,
            "response_time_ms": project.response_time_ms,
            "last_checked_at": project.last_checked_at,
            "expiry_date": project.expiry_date,
            "days_remaining": (project.expiry_date - timezone.localdate()).days,
        }
        _log_hosting_api_usage(request, api_key, status.HTTP_200_OK, started)
        return Response(payload)

    @action(detail=False, methods=["post"], url_path="external-toggle", permission_classes=[AllowAny])
    def external_toggle(self, request):
        started = time.perf_counter()
        api_key, error = _validate_hosting_api_key(request, required_permission=HostingProjectApiKey.Permission.WRITE)
        if error:
            return Response(error, status=error.get("status", status.HTTP_401_UNAUTHORIZED))
        enabled = request.data.get("enabled")
        if enabled is None:
            enabled = request.data.get("link_is_active")
        if isinstance(enabled, str):
            enabled = enabled.lower() in {"1", "true", "yes", "on", "active"}
        project = api_key.project
        project.link_is_active = bool(enabled)
        project.status = HostedProject.Status.LIVE if enabled else HostedProject.Status.SUSPENDED
        project.tag = "active" if enabled else "maintenance"
        project.save(update_fields=["link_is_active", "status", "tag"])
        active_link = project.failover_state.active_link if hasattr(project, "failover_state") else None
        if active_link:
            try:
                toggle_hosting_link(active_link, bool(enabled), user=request.user)
            except ProviderError:
                pass
        HostingLifecycle.objects.create(
            project=project,
            event_type=HostingLifecycle.Event.LINK_ENABLED if enabled else HostingLifecycle.Event.LINK_DISABLED,
            notes="External API toggled hosting access.",
        )
        _log_hosting_api_usage(request, api_key, status.HTTP_200_OK, started)
        return Response({"project": project.name, "domain": project.domain, "link_is_active": project.link_is_active, "status": project.status})

    @action(detail=False, methods=["get"], url_path="expiring-soon")
    def expiring_soon(self, request):
        today = timezone.localdate()
        rows = self.get_queryset().filter(expiry_date__gte=today, expiry_date__lte=today + timedelta(days=60)).order_by("expiry_date")
        return Response(self.get_serializer(rows, many=True).data)


class HostingLifecycleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = HostingLifecycle.objects.select_related("project", "performed_by")
    serializer_class = HostingLifecycleSerializer
    filterset_fields = ["project", "event_type"]


class HostingProjectApiKeyViewSet(viewsets.ModelViewSet):
    queryset = HostingProjectApiKey.objects.select_related("project", "created_by")
    serializer_class = HostingProjectApiKeySerializer
    filterset_fields = ["project", "role", "is_active"]
    search_fields = ["name", "key_prefix", "project__name", "project__domain"]

    def perform_create(self, serializer):
        obj = serializer.save()
        audit_event(self.request, "hosting.api_key_created", "HostingProjectApiKey", obj.id, {"project": obj.project_id, "role": obj.role})

    @action(detail=True, methods=["post"])
    def regenerate(self, request, pk=None):
        api_key = self.get_object()
        plaintext = f"host_{timezone.now().strftime('%Y%m%d')}_{api_key.id.hex[:18]}"
        api_key.key_encrypted = _fernet().encrypt(plaintext.encode()).decode()
        api_key.key_prefix = plaintext[5:17]
        api_key.save(update_fields=["key_encrypted", "key_prefix", "updated_at"])
        data = self.get_serializer(api_key).data
        data["plaintext_key"] = plaintext
        data["warning"] = "Store this key securely. It will not be shown again."
        audit_event(request, "hosting.api_key_regenerated", "HostingProjectApiKey", api_key.id, {"project": api_key.project_id})
        return Response(data)

    @action(detail=True, methods=["post"])
    def toggle(self, request, pk=None):
        api_key = self.get_object()
        api_key.is_active = not api_key.is_active
        api_key.save(update_fields=["is_active", "updated_at"])
        audit_event(request, "hosting.api_key_toggled", "HostingProjectApiKey", api_key.id, {"is_active": api_key.is_active})
        return Response(self.get_serializer(api_key).data)

    @action(detail=True, methods=["get"])
    def logs(self, request, pk=None):
        logs = self.get_object().usage_logs.all()[:100]
        return Response(HostingApiUsageLogSerializer(logs, many=True).data)


class HostingProviderViewSet(viewsets.ModelViewSet):
    queryset = HostingProvider.objects.prefetch_related("links")
    serializer_class = HostingProviderSerializer
    filterset_fields = ["provider", "priority", "is_enabled"]
    search_fields = ["name", "provider"]
    ordering_fields = ["priority", "name", "last_synced_at"]

    @action(detail=False, methods=["post"])
    def sync(self, request):
        try:
            results = sync_all_providers()
        except ProviderError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        audit_event(request, "hosting.providers_synced", "HostingProvider", metadata=results)
        return Response(results)


class EmailAccountViewSet(viewsets.ModelViewSet):
    queryset = EmailAccount.objects.select_related("project", "hosting_link")
    serializer_class = EmailAccountSerializer
    filterset_fields = ["project", "provider", "status", "mx_status"]
    search_fields = ["email", "display_name", "project__name", "project__domain"]
    ordering_fields = ["email", "provider", "used_mb", "quota_mb", "last_checked_at"]

    def perform_destroy(self, instance):
        HostingLifecycle.objects.create(project=instance.project, event_type=HostingLifecycle.Event.EMAIL_DELETED, notes=f"{instance.email} deleted.")
        audit_event(self.request, "hosting.email_deleted", "EmailAccount", instance.id, {"email": instance.email})
        return super().perform_destroy(instance)

    @action(detail=True, methods=["post"])
    def check(self, request, pk=None):
        from .tasks import check_email_account

        account = self.get_object()
        check_email_account.delay(account.id)
        return Response({"detail": "Email account check queued."})


class DomainStatusViewSet(viewsets.ModelViewSet):
    queryset = DomainStatus.objects.select_related("project")
    serializer_class = DomainStatusSerializer
    filterset_fields = ["project", "mx_status", "ssl_status"]
    search_fields = ["domain", "project__name", "project__domain"]
    ordering_fields = ["domain", "last_checked_at", "domain_expires_at", "ssl_expires_at"]

    @action(detail=True, methods=["post"])
    def check(self, request, pk=None):
        from .tasks import check_domain_status

        domain = self.get_object()
        check_domain_status.delay(domain.project_id)
        return Response({"detail": "Domain check queued."})


class ProjectUploadViewSet(viewsets.ModelViewSet):
    queryset = ProjectUpload.objects.select_related("owner", "project").prefetch_related("deployments")
    serializer_class = ProjectUploadSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filterset_fields = ["status", "project_type"]
    search_fields = ["original_name", "project__name", "project__domain"]

    def perform_create(self, serializer):
        upload = serializer.save()
        from .tasks import analyze_project_upload

        analyze_project_upload.delay(str(upload.id))

    @action(detail=True, methods=["post"])
    def analyze(self, request, pk=None):
        from .tasks import analyze_project_upload

        upload = self.get_object()
        analyze_project_upload.delay(str(upload.id))
        return Response({"detail": "Project analysis queued.", "upload": str(upload.id)})

    @action(detail=True, methods=["post"])
    def deploy(self, request, pk=None):
        upload = self.get_object()
        deployment = DeploymentRun.objects.create(
            upload=upload,
            project=upload.project,
            primary_provider=request.data.get("primary_provider", "vercel"),
            backup_provider=request.data.get("backup_provider", ""),
            domain=request.data.get("domain", ""),
            build_command=request.data.get("build_command", ""),
            output_directory=request.data.get("output_directory", ""),
            environment=request.data.get("environment", {}),
            created_by=request.user if request.user.is_authenticated else None,
        )
        from .tasks import run_project_deployment

        run_project_deployment.delay(str(deployment.id))
        return Response(DeploymentRunSerializer(deployment).data, status=status.HTTP_201_CREATED)


class DeploymentRunViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DeploymentRun.objects.select_related("upload", "project", "created_by")
    serializer_class = DeploymentRunSerializer
    filterset_fields = ["status", "primary_provider", "backup_provider", "project"]
    search_fields = ["upload__original_name", "project__name", "domain", "live_url"]

    @action(detail=True, methods=["post"])
    def redeploy(self, request, pk=None):
        deployment = self.get_object()
        new_run = DeploymentRun.objects.create(
            upload=deployment.upload,
            project=deployment.project,
            primary_provider=request.data.get("primary_provider", deployment.primary_provider),
            backup_provider=request.data.get("backup_provider", deployment.backup_provider),
            domain=request.data.get("domain", deployment.domain),
            build_command=request.data.get("build_command", deployment.build_command),
            output_directory=request.data.get("output_directory", deployment.output_directory),
            environment=request.data.get("environment", deployment.environment),
            created_by=request.user if request.user.is_authenticated else None,
        )
        from .tasks import run_project_deployment

        run_project_deployment.delay(str(new_run.id))
        return Response(DeploymentRunSerializer(new_run).data, status=status.HTTP_201_CREATED)


class HostingLinkViewSet(viewsets.ModelViewSet):
    queryset = HostingLink.objects.select_related("project", "provider_config")
    serializer_class = HostingLinkSerializer
    filterset_fields = ["project", "provider", "priority", "status", "health_status", "is_active", "is_enabled"]
    search_fields = ["project__name", "label", "domain", "url", "external_id"]
    ordering_fields = ["priority", "provider", "last_checked_at", "uptime_percentage"]

    @action(detail=True, methods=["post"])
    def toggle(self, request, pk=None):
        link = self.get_object()
        enabled = request.data.get("enabled", request.data.get("status", "on"))
        if isinstance(enabled, str):
            enabled = enabled.lower() in {"1", "true", "yes", "on", "active"}
        try:
            toggle_hosting_link(link, bool(enabled), user=request.user)
        except ProviderError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        audit_event(request, "hosting.provider_toggled", "HostingLink", link.id, {"enabled": bool(enabled), "provider": link.provider})
        return Response(self.get_serializer(link).data)


class HostingFailoverViewSet(viewsets.ViewSet):
    def list(self, request):
        states = [evaluate_failover(project) for project in HostedProject.objects.prefetch_related("hosting_links")]
        return Response(HostingFailoverStateSerializer(states, many=True).data)

    def create(self, request):
        project_id = request.data.get("project") or request.data.get("project_id")
        if project_id:
            try:
                state = evaluate_failover(HostedProject.objects.get(id=project_id))
            except HostedProject.DoesNotExist:
                return Response({"detail": "Project not found."}, status=status.HTTP_404_NOT_FOUND)
            audit_event(request, "hosting.failover_evaluated", "HostedProject", project_id)
            return Response(HostingFailoverStateSerializer(state).data)
        states = failover_all_projects()
        audit_event(request, "hosting.failover_all", "HostedProject", metadata={"count": len(states)})
        return Response(HostingFailoverStateSerializer(states, many=True).data)


class VercelProjectViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = VercelProject.objects.select_related("hosted_project", "hosting_status").prefetch_related("links", "deployments")
    serializer_class = VercelProjectSerializer
    search_fields = ["name", "production_domain", "latest_deployment_url", "links__domain"]
    filterset_fields = ["latest_deployment_status", "framework", "team_id", "hosting_status__is_enabled"]
    ordering_fields = ["name", "last_synced_at", "updated_at"]

    @action(detail=False, methods=["post"])
    def sync(self, request):
        try:
            synced = sync_vercel_projects()
        except VercelApiError as exc:
            return Response({"detail": str(exc), "payload": exc.payload}, status=exc.status_code or status.HTTP_502_BAD_GATEWAY)
        audit_event(request, "hosting.vercel_synced", "VercelProject", metadata={"count": len(synced)})
        return Response({"detail": "Vercel projects synced.", "count": len(synced)})

    @action(detail=False, methods=["post"], url_path="toggle")
    def toggle_by_lookup(self, request):
        lookup = request.data.get("project") or request.data.get("project_id") or request.data.get("vercel_id") or request.data.get("domain")
        if not lookup:
            return Response({"detail": "project, project_id, vercel_id, or domain is required."}, status=status.HTTP_400_BAD_REQUEST)
        queryset = self.get_queryset()
        project = (
            queryset.filter(id=lookup).first()
            if str(lookup).isdigit()
            else queryset.filter(vercel_id=lookup).first()
            or queryset.filter(name=lookup).first()
            or queryset.filter(links__domain=lookup).first()
            or queryset.filter(production_domain=lookup).first()
        )
        if not project:
            return Response({"detail": "Vercel project not found."}, status=status.HTTP_404_NOT_FOUND)
        self.kwargs["pk"] = project.pk
        return self.toggle(request, pk=project.pk)

    @action(detail=True, methods=["post"])
    def deployments(self, request, pk=None):
        project = self.get_object()
        try:
            rows = sync_project_deployments(project)
        except VercelApiError as exc:
            return Response({"detail": str(exc), "payload": exc.payload}, status=exc.status_code or status.HTTP_502_BAD_GATEWAY)
        return Response(VercelDeploymentSerializer(rows, many=True).data)

    @action(detail=True, methods=["post"])
    def redeploy(self, request, pk=None):
        project = self.get_object()
        deployment_id = request.data.get("deployment_id") or project.latest_deployment_id
        if not deployment_id:
            return Response({"detail": "No deployment_id is available to redeploy."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            payload = VercelClient(team_id=project.team_id).redeploy(deployment_id)
            sync_project_deployments(project)
        except VercelApiError as exc:
            return Response({"detail": str(exc), "payload": exc.payload}, status=exc.status_code or status.HTTP_502_BAD_GATEWAY)
        if project.hosted_project:
            HostingLifecycle.objects.create(
                project=project.hosted_project,
                event_type=HostingLifecycle.Event.VERCEL_REDEPLOY,
                performed_by=request.user if request.user.is_authenticated else None,
                notes=f"Redeploy requested for {deployment_id}.",
            )
        audit_event(request, "hosting.vercel_redeploy", "VercelProject", project.id, {"deployment_id": deployment_id})
        return Response({"detail": "Redeploy requested.", "payload": payload})

    @action(detail=True, methods=["get"], url_path="logs")
    def logs(self, request, pk=None):
        project = self.get_object()
        deployment_id = request.query_params.get("deployment_id") or project.latest_deployment_id
        if not deployment_id:
            return Response({"detail": "No deployment_id is available for logs."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            payload = VercelClient(team_id=project.team_id).deployment_events(deployment_id)
        except VercelApiError as exc:
            return Response({"detail": str(exc), "payload": exc.payload}, status=exc.status_code or status.HTTP_502_BAD_GATEWAY)
        return Response(payload)

    @action(detail=True, methods=["post"])
    def toggle(self, request, pk=None):
        project = self.get_object()
        enabled = request.data.get("enabled", request.data.get("link_is_active", True))
        if isinstance(enabled, str):
            enabled = enabled.lower() in {"1", "true", "yes", "on", "active"}
        try:
            status_obj, errors = set_vercel_access(
                project,
                bool(enabled),
                user=request.user,
                redirect_url=request.data.get("redirect_url", ""),
                reason=request.data.get("reason", ""),
            )
        except VercelApiError as exc:
            return Response({"detail": str(exc), "payload": exc.payload}, status=exc.status_code or status.HTTP_502_BAD_GATEWAY)
        if project.hosted_project:
            HostingLifecycle.objects.create(
                project=project.hosted_project,
                event_type=HostingLifecycle.Event.LINK_ENABLED if enabled else HostingLifecycle.Event.LINK_DISABLED,
                performed_by=request.user if request.user.is_authenticated else None,
                notes="Vercel access restored." if enabled else "Vercel project domains removed to simulate hosting OFF.",
            )
        audit_event(request, "hosting.vercel_toggled", "VercelProject", project.id, {"enabled": bool(enabled), "errors": errors})
        data = HostingStatusSerializer(status_obj).data
        data["domain_errors"] = errors
        return Response(data, status=status.HTTP_207_MULTI_STATUS if errors else status.HTTP_200_OK)


class VercelDeploymentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = VercelDeployment.objects.select_related("project")
    serializer_class = VercelDeploymentSerializer
    filterset_fields = ["project", "status", "target"]
    search_fields = ["deployment_id", "url", "project__name"]


def _validate_hosting_api_key(request, required_permission=HostingProjectApiKey.Permission.READ):
    auth = request.headers.get("Authorization", "")
    plaintext = auth.removeprefix("API_KEY ").strip() if auth.startswith("API_KEY ") else request.query_params.get("api_key", "")
    if not plaintext.startswith("host_") or len(plaintext) <= 17:
        return None, {"detail": "Invalid hosting API key.", "status": status.HTTP_401_UNAUTHORIZED}
    prefix = plaintext[5:17]
    for api_key in HostingProjectApiKey.objects.select_related("project").filter(key_prefix=prefix, is_active=True):
        try:
            if _fernet().decrypt(api_key.key_encrypted.encode()).decode() != plaintext:
                continue
        except Exception:
            continue
        if api_key.expires_at and api_key.expires_at <= timezone.now():
            return None, {"detail": "Hosting API key expired.", "status": status.HTTP_401_UNAUTHORIZED}
        if required_permission == HostingProjectApiKey.Permission.WRITE and api_key.permission_level != HostingProjectApiKey.Permission.WRITE and api_key.role != HostingProjectApiKey.Role.ADMIN:
            return None, {"detail": "Write permission is required.", "status": status.HTTP_403_FORBIDDEN}
        cache_key = f"hosting-ratelimit:{api_key.id}:{int(time.time() // 60)}"
        try:
            count = cache.incr(cache_key)
        except ValueError:
            cache.set(cache_key, 1, 60)
            count = 1
        except Exception:
            count = 1
        if count > api_key.rate_limit_per_minute:
            return None, {"detail": "Rate limit exceeded.", "status": status.HTTP_429_TOO_MANY_REQUESTS}
        api_key.last_used_at = timezone.now()
        api_key.save(update_fields=["last_used_at", "updated_at"])
        return api_key, None
    return None, {"detail": "Invalid hosting API key.", "status": status.HTTP_401_UNAUTHORIZED}


def _log_hosting_api_usage(request, api_key, response_code, started):
    elapsed = int((time.perf_counter() - started) * 1000)
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    ip_address = (forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")) or "127.0.0.1"
    try:
        HostingApiUsageLog.objects.create(api_key=api_key, endpoint=request.path, http_method=request.method, ip_address=ip_address, response_code=response_code, response_time_ms=elapsed)
    except Exception:
        pass


def _provider_error_response(exc):
    return Response(
        {
            "success": False,
            "data": None,
            "status": "down",
            "detail": str(exc),
            "message": "API Not Connected" if exc.code in {"missing_credentials", "api_not_connected"} else str(exc),
            "error": exc.code,
            "payload": exc.payload,
        },
        status=exc.status_code,
    )


def _provider_success_response(data, status_value="running"):
    return Response({"success": True, "data": data, "status": status_value})


def _status_value(payload):
    if not payload:
        return "running"
    if isinstance(payload, str):
        text = payload
    else:
        text = payload.get("state") or payload.get("server_status") or payload.get("status") or ""
    return "down" if str(text).lower() in {"offline", "down", "error", "suspended", "maintenance"} else "running"
