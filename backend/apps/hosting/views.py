from datetime import timedelta
import csv
import logging
import math
import re
import shutil
import socket
import time
from pathlib import Path

import requests
from django.conf import settings
from django.core.cache import cache
from django.core.files import File
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
from apps.projects.services import sync_project_from_hosting

from .models import DeploymentRun, DomainStatus, EmailAccount, HostedProject, HostingApiUsageLog, HostingHealthCheck, HostingIncident, HostingLifecycle, HostingProjectApiKey, HostingLink, HostingProvider, HostingStatus, ProjectUpload, ProjectUploadSession, VercelDeployment, VercelProject
from .netlify import NetlifyApiError, NetlifyClient, get_netlify_status
from .health import probe_url
from .providers import ProviderError, evaluate_failover, failover_all_projects, sync_all_providers, toggle_hosted_project_access, toggle_hosting_link
from .services import ProviderConnectionError, get_service
from .serializers import (
    HostedProjectSerializer,
    DeploymentRunSerializer,
    DomainStatusSerializer,
    EmailAccountSerializer,
    HostingFailoverStateSerializer,
    HostingApiUsageLogSerializer,
    HostingHealthCheckSerializer,
    HostingIncidentSerializer,
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


logger = logging.getLogger(__name__)


SELECTABLE_UPLOAD_PROVIDERS = {
    "aws",
    "azure",
    "gcp",
    "vercel",
    "netlify",
    "cloudflare",
}
UPLOAD_DEPLOYMENT_ADAPTERS = {"aws", "azure", "gcp", "vercel", "netlify", "cloudflare"}
PROVIDER_ALIASES = {
    "aws": "aws",
    "azure": "azure",
    "google": "gcp",
    "google_cloud": "gcp",
    "google-cloud": "gcp",
    "gcp": "gcp",
    "railway": "railway",
    "render": "render",
    "vercel": "vercel",
    "netlify": "netlify",
    "firebase": "firebase",
    "fly": "fly",
    "fly_io": "fly",
    "fly.io": "fly",
    "digitalocean": "digitalocean",
    "digital_ocean": "digitalocean",
    "hostinger": "hostinger",
    "cloudflare": "cloudflare",
    "cloudflare_pages": "cloudflare",
    "github": "github",
    "github_deployments": "github",
    "cpanel": "cpanel",
    "plesk": "plesk",
}
PROVIDER_SECRET_REQUIREMENTS = {
    "aws": [("AWS_ACCESS_KEY_ID", "AWS_ACCESS_KEY"), ("AWS_SECRET_ACCESS_KEY", "AWS_SECRET_KEY"), ("AWS_DEPLOYMENT_BUCKET", "AWS_STORAGE_BUCKET_NAME")],
    "azure": [("AZURE_CLIENT_ID",), ("AZURE_CLIENT_SECRET",), ("AZURE_TENANT_ID",), ("AZURE_SUBSCRIPTION_ID",), ("AZURE_RESOURCE_GROUP",), ("AZURE_APP_SERVICE_NAME",)],
    "gcp": [("GCP_PROJECT_ID",), ("GCP_STORAGE_BUCKET",), ("GCP_ACCESS_TOKEN", "GCP_SERVICE_ACCOUNT_JSON", "GOOGLE_APPLICATION_CREDENTIALS")],
    "vercel": [("VERCEL_TOKEN", "VERCEL_API_TOKEN")],
    "netlify": [("NETLIFY_TOKEN", "NETLIFY_API_TOKEN"), ("NETLIFY_SITE_ID",)],
    "cloudflare": [("CLOUDFLARE_API_TOKEN",), ("CLOUDFLARE_ACCOUNT_ID",), ("CLOUDFLARE_PAGES_PROJECT_NAME",)],
}
DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?!-)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


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
        sync_project_from_hosting(obj, actor=self.request.user if self.request.user.is_authenticated else None)
        audit_event(self.request, "hosting.created", "HostedProject", obj.id, {"domain": obj.domain})

    def perform_update(self, serializer):
        obj = serializer.save()
        sync_project_from_hosting(obj, actor=self.request.user if self.request.user.is_authenticated else None)
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
        sync_project_from_hosting(project, actor=request.user if request.user.is_authenticated else None)
        audit_event(request, "hosting.renewed", "HostedProject", project.id, {"old_expiry": str(old_expiry), "new_expiry": str(project.expiry_date)})
        return Response(self.get_serializer(project).data)

    @action(detail=True, methods=["post", "patch"])
    def toggle_link(self, request, pk=None):
        project = self.get_object()
        force_state = request.data.get("link_is_active")
        if force_state is None:
            force_state = request.data.get("enabled")
        if isinstance(force_state, str):
            force_state = force_state.lower() in {"1", "true", "yes", "on"}
        enabled = (not project.link_is_active) if force_state is None else bool(force_state)
        try:
            project = toggle_hosted_project_access(
                project,
                enabled,
                user=request.user,
                reason=request.data.get("reason", ""),
            )
        except ProviderError as exc:
            return Response({"detail": str(exc), "errors": exc.details}, status=status.HTTP_502_BAD_GATEWAY)
        audit_event(request, "hosting.link_toggled", "HostedProject", project.id, {"link_is_active": project.link_is_active, "status": project.status})
        return Response(self.get_serializer(project).data)

    @action(detail=True, methods=["post"], url_path="health-check")
    def health_check(self, request, pk=None):
        from .tasks import check_hosted_project_health

        project = self.get_object()
        check_hosted_project_health.delay(project.id)
        return Response({"detail": "Health check queued."})

    @action(detail=False, methods=["post"], url_path="refresh-status")
    def refresh_status(self, request):
        from .tasks import check_all_hosted_project_health, check_vercel_links

        health_task_id, health_warning = _queue_task_safely(check_all_hosted_project_health, "hosting health refresh")
        vercel_task_id, vercel_warning = _queue_task_safely(check_vercel_links, "Vercel link refresh")
        cache_status = _invalidate_hosting_refresh_cache()
        warnings = [item for item in [health_warning, vercel_warning, cache_status.get("warning")] if item]
        payload = {
            "detail": "Status refresh queued." if not warnings else "Status refresh accepted with warnings.",
            "health_task": health_task_id,
            "vercel_task": vercel_task_id,
            "cache": cache_status,
            "warnings": warnings,
        }
        audit_event(
            request,
            "hosting.status_refresh",
            "HostedProject",
            metadata={
                "health_task": health_task_id,
                "vercel_task": vercel_task_id,
                "warnings": warnings,
            },
        )
        return Response(payload, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        project = self.get_object()
        project.archived_at = timezone.now()
        project.status = HostedProject.Status.EXPIRED
        project.tag = "expired"
        project.link_is_active = False
        project.save(update_fields=["archived_at", "status", "tag", "link_is_active"])
        HostingLifecycle.objects.create(project=project, event_type=HostingLifecycle.Event.ARCHIVED, performed_by=request.user, notes=request.data.get("notes", "Archived from Hosting Manager"))
        sync_project_from_hosting(project, actor=request.user if request.user.is_authenticated else None)
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
        sync_project_from_hosting(project, actor=request.user if request.user.is_authenticated else None)
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
        try:
            project = toggle_hosted_project_access(project, bool(enabled), reason="External API toggled hosting access.", source="hosting.external_api")
        except ProviderError as exc:
            _log_hosting_api_usage(request, api_key, status.HTTP_502_BAD_GATEWAY, started)
            return Response({"detail": str(exc), "errors": exc.details}, status=status.HTTP_502_BAD_GATEWAY)
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


class HostingHealthCheckViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = HostingHealthCheck.objects.select_related("project", "hosting_link", "vercel_link")
    serializer_class = HostingHealthCheckSerializer
    filterset_fields = ["project", "target_type", "is_online", "status_code"]
    ordering_fields = ["checked_at", "response_time_ms", "status_code"]


class HostingIncidentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = HostingIncident.objects.select_related("project", "hosting_link", "vercel_link")
    serializer_class = HostingIncidentSerializer
    filterset_fields = ["project", "status"]
    ordering_fields = ["started_at", "resolved_at", "downtime_seconds", "failure_count"]


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

    @action(detail=False, methods=["post"], url_path="chunk/initiate")
    def initiate_chunk_upload(self, request):
        original_name = _safe_upload_filename(request.data.get("original_name") or request.data.get("name") or "project-upload.zip")
        try:
            size_bytes = _positive_int(request.data.get("size_bytes"), "size_bytes")
            chunk_size = min(max(_positive_int(request.data.get("chunk_size") or 5 * 1024 * 1024, "chunk_size"), 1024 * 1024), 25 * 1024 * 1024)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if size_bytes > _max_project_upload_bytes():
            return Response({"detail": f"Project uploads are limited to {_max_project_upload_bytes() // (1024 * 1024)}MB."}, status=status.HTTP_400_BAD_REQUEST)
        total_chunks = max(1, math.ceil(size_bytes / chunk_size))
        session = ProjectUploadSession.objects.create(
            owner=request.user if request.user.is_authenticated else None,
            original_name=original_name,
            source_type=str(request.data.get("source_type") or "file")[:32],
            size_bytes=size_bytes,
            chunk_size=chunk_size,
            total_chunks=total_chunks,
            expires_at=timezone.now() + timedelta(days=2),
        )
        temp_dir = _upload_session_dir(session)
        temp_dir.mkdir(parents=True, exist_ok=True)
        session.temp_dir = str(temp_dir)
        session.save(update_fields=["temp_dir", "updated_at"])
        return Response(_upload_session_payload(session), status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="chunk/status")
    def chunk_status(self, request):
        session = _get_upload_session(request)
        if not session:
            return Response({"detail": "Upload session not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(_upload_session_payload(session))

    @action(detail=False, methods=["post"], url_path="chunk/upload")
    def upload_chunk(self, request):
        session = _get_upload_session(request)
        if not session:
            return Response({"detail": "Upload session not found."}, status=status.HTTP_404_NOT_FOUND)
        if session.status in {ProjectUploadSession.Status.CANCELLED, ProjectUploadSession.Status.COMPLETED}:
            return Response({"detail": f"Upload session is {session.status}."}, status=status.HTTP_409_CONFLICT)
        try:
            chunk_index = _positive_int(request.data.get("chunk_index"), "chunk_index", allow_zero=True)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if chunk_index < 0 or chunk_index >= session.total_chunks:
            return Response({"detail": "Chunk index is out of range."}, status=status.HTTP_400_BAD_REQUEST)
        chunk = request.FILES.get("chunk") or request.FILES.get("file")
        if not chunk:
            return Response({"detail": "Chunk file is required."}, status=status.HTTP_400_BAD_REQUEST)
        temp_dir = Path(session.temp_dir or _upload_session_dir(session))
        temp_dir.mkdir(parents=True, exist_ok=True)
        chunk_path = temp_dir / f"{chunk_index:08d}.part"
        with chunk_path.open("wb") as destination:
            for piece in chunk.chunks():
                destination.write(piece)
        received = session.completed_chunk_numbers
        received.add(chunk_index)
        session.received_chunks = sorted(received)
        session.status = ProjectUploadSession.Status.UPLOADING
        session.save(update_fields=["received_chunks", "status", "updated_at"])
        return Response(_upload_session_payload(session))

    @action(detail=False, methods=["post"], url_path="chunk/complete")
    def complete_chunk_upload(self, request):
        session = _get_upload_session(request)
        if not session:
            return Response({"detail": "Upload session not found."}, status=status.HTTP_404_NOT_FOUND)
        if session.missing_chunks:
            return Response({"detail": "Upload session is missing chunks.", "missing_chunks": session.missing_chunks}, status=status.HTTP_400_BAD_REQUEST)
        try:
            upload = _complete_upload_session(session, request)
        except Exception as exc:
            session.status = ProjectUploadSession.Status.FAILED
            session.error_message = str(exc)
            session.save(update_fields=["status", "error_message", "updated_at"])
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        from .tasks import analyze_project_upload

        analyze_project_upload.delay(str(upload.id))
        return Response(ProjectUploadSerializer(upload, context={"request": request}).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="chunk/cancel")
    def cancel_chunk_upload(self, request):
        session = _get_upload_session(request)
        if not session:
            return Response({"detail": "Upload session not found."}, status=status.HTTP_404_NOT_FOUND)
        session.status = ProjectUploadSession.Status.CANCELLED
        session.save(update_fields=["status", "updated_at"])
        if session.temp_dir:
            shutil.rmtree(session.temp_dir, ignore_errors=True)
        return Response(_upload_session_payload(session))

    @action(detail=True, methods=["post"])
    def deploy(self, request, pk=None):
        upload = self.get_object()
        requested_primary = request.data.get("primary_provider")
        if not requested_primary:
            return Response(
                {
                    "detail": "primary_provider is required. Select a hosting provider before deployment.",
                    "fallback_provider": None,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        primary_provider = _normalize_upload_provider(requested_primary)
        backup_provider = _normalize_upload_provider(request.data.get("backup_provider") or "", allow_blank=True)
        if primary_provider not in SELECTABLE_UPLOAD_PROVIDERS:
            return Response(
                {
                    "detail": f"Unsupported hosting provider '{primary_provider}'.",
                    "provider": primary_provider,
                    "allowed_providers": sorted(SELECTABLE_UPLOAD_PROVIDERS),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        deployment = DeploymentRun.objects.create(
            upload=upload,
            project=upload.project,
            primary_provider=primary_provider,
            backup_provider=backup_provider,
            domain=request.data.get("domain", ""),
            build_command=request.data.get("build_command", ""),
            output_directory=request.data.get("output_directory", ""),
            environment=request.data.get("environment", {}),
            status=DeploymentRun.Status.CONFIGURING,
            progress=8,
            created_by=request.user if request.user.is_authenticated else None,
        )
        _append_deployment_api_log(deployment, f"Deployment record created for selected provider: {_provider_label(primary_provider)}.")
        if primary_provider not in UPLOAD_DEPLOYMENT_ADAPTERS:
            return _failed_deployment_response(deployment, _provider_adapter_error(primary_provider), http_status=status.HTTP_400_BAD_REQUEST)
        preflight_error = _deployment_preflight_error(upload, request.data, primary_provider)
        if preflight_error:
            return _failed_deployment_response(deployment, preflight_error, http_status=status.HTTP_400_BAD_REQUEST)
        deployment.status = DeploymentRun.Status.QUEUED
        deployment.progress = 12
        _append_deployment_api_log(deployment, "Deployment passed preflight validation and was queued.", save=False)
        deployment.save(update_fields=["status", "progress", "logs"])
        from .tasks import run_project_deployment

        run_project_deployment.delay(str(deployment.id))
        return Response(DeploymentRunSerializer(deployment).data, status=status.HTTP_201_CREATED)


class DeploymentRunViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DeploymentRun.objects.select_related("upload", "project", "created_by")
    serializer_class = DeploymentRunSerializer
    filterset_fields = ["status", "primary_provider", "backup_provider", "project"]
    search_fields = ["upload__original_name", "project__name", "domain", "live_url"]

    @action(detail=True, methods=["get"])
    def logs(self, request, pk=None):
        deployment = self.get_object()
        provider_logs = []
        if deployment.primary_provider == HostingLink.Provider.VERCEL and deployment.provider_deployment_id:
            try:
                provider_logs = VercelClient().deployment_events(deployment.provider_deployment_id)
            except VercelApiError as exc:
                return Response({"detail": str(exc), "deployment": DeploymentRunSerializer(deployment).data, "logs": deployment.logs}, status=exc.status_code or status.HTTP_502_BAD_GATEWAY)
        elif deployment.primary_provider == HostingLink.Provider.NETLIFY and deployment.provider_deployment_id:
            token = getattr(settings, "NETLIFY_API_TOKEN", "")
            if not token:
                return Response({"detail": "NETLIFY_API_TOKEN or NETLIFY_TOKEN is required for Netlify provider logs.", "deployment": DeploymentRunSerializer(deployment).data, "logs": deployment.logs}, status=status.HTTP_400_BAD_REQUEST)
            response = requests.get(f"https://api.netlify.com/api/v1/deploys/{deployment.provider_deployment_id}", headers={"Authorization": f"Bearer {token}"}, timeout=30)
            try:
                payload = response.json() if response.content else {}
            except ValueError:
                payload = {"detail": response.text}
            if response.status_code >= 400:
                return Response({"detail": payload.get("message") or payload.get("detail") or response.text, "deployment": DeploymentRunSerializer(deployment).data, "logs": deployment.logs}, status=response.status_code)
            provider_logs = [payload]
        elif deployment.primary_provider == "azure" and deployment.provider_deployment_id:
            try:
                token = _azure_access_token_for_logs()
            except ValueError as exc:
                return Response({"detail": str(exc), "deployment": DeploymentRunSerializer(deployment).data, "logs": deployment.logs}, status=status.HTTP_400_BAD_REQUEST)
            app_name = _setting_first("AZURE_APP_SERVICE_NAME")
            if not app_name:
                return Response({"detail": "AZURE_APP_SERVICE_NAME is required for Azure provider logs.", "deployment": DeploymentRunSerializer(deployment).data, "logs": deployment.logs}, status=status.HTTP_400_BAD_REQUEST)
            response = requests.get(
                f"https://{app_name}.scm.azurewebsites.net/api/deployments/{deployment.provider_deployment_id}/log",
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            )
            payload = _provider_response_payload(response)
            if response.status_code >= 400:
                return Response({"detail": _provider_response_message(payload, response, "Azure provider logs failed."), "deployment": DeploymentRunSerializer(deployment).data, "logs": deployment.logs}, status=response.status_code)
            provider_logs = payload if isinstance(payload, list) else [payload]
        elif deployment.primary_provider == HostingLink.Provider.CLOUDFLARE and deployment.provider_deployment_id:
            account_id = _setting_first("CLOUDFLARE_ACCOUNT_ID")
            project_name = _setting_first("CLOUDFLARE_PAGES_PROJECT_NAME")
            token = _setting_first("CLOUDFLARE_API_TOKEN")
            if not all([account_id, project_name, token]):
                return Response({"detail": "CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID, and CLOUDFLARE_PAGES_PROJECT_NAME are required for Cloudflare provider logs.", "deployment": DeploymentRunSerializer(deployment).data, "logs": deployment.logs}, status=status.HTTP_400_BAD_REQUEST)
            response = requests.get(
                f"https://api.cloudflare.com/client/v4/accounts/{account_id}/pages/projects/{project_name}/deployments/{deployment.provider_deployment_id}/history/logs",
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            )
            payload = _provider_response_payload(response)
            if response.status_code >= 400:
                return Response({"detail": _provider_response_message(payload, response, "Cloudflare provider logs failed."), "deployment": DeploymentRunSerializer(deployment).data, "logs": deployment.logs}, status=response.status_code)
            provider_logs = payload.get("result", payload) if isinstance(payload, dict) else payload
        elif deployment.status not in {DeploymentRun.Status.FAILED, DeploymentRun.Status.ERROR} and not deployment.provider_deployment_id:
            return Response(
                {
                    "detail": "Provider deployment id is not available yet. Wait for the provider API to create the deployment resource.",
                    "deployment": DeploymentRunSerializer(deployment).data,
                    "logs": deployment.logs,
                    "provider_logs": [],
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response({"deployment": DeploymentRunSerializer(deployment).data, "logs": deployment.logs, "provider_logs": provider_logs})

    @action(detail=True, methods=["get"])
    def metrics(self, request, pk=None):
        deployment = self.get_object()
        if not deployment.live_url:
            return Response({"detail": "Deployment has no live_url yet.", "deployment": DeploymentRunSerializer(deployment).data}, status=status.HTTP_400_BAD_REQUEST)
        result = probe_url(deployment.live_url, timeout=8, retries=2)
        metrics = {
            "latency_ms": result.response_time_ms,
            "response_time_ms": result.response_time_ms,
            "health": "healthy" if result.online else "down",
            "http_status": result.status_code,
            "dns_ok": result.dns_ok,
            "ssl_ok": result.ssl_ok,
            "checked_at": timezone.now().isoformat(),
        }
        deployment.metrics = metrics
        deployment.save(update_fields=["metrics"])
        return Response({"deployment": DeploymentRunSerializer(deployment).data, "metrics": metrics})

    @action(detail=True, methods=["post"])
    def redeploy(self, request, pk=None):
        deployment = self.get_object()
        requested_provider = _normalize_upload_provider(request.data.get("primary_provider") or deployment.primary_provider)
        if requested_provider != deployment.primary_provider:
            return Response(
                {
                    "detail": f"Redeploy uses the original selected provider {deployment.primary_provider}. Create a new deployment target to use {requested_provider}.",
                    "selected_provider": deployment.primary_provider,
                    "requested_provider": requested_provider,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        new_run = DeploymentRun.objects.create(
            upload=deployment.upload,
            project=deployment.project,
            primary_provider=deployment.primary_provider,
            backup_provider=request.data.get("backup_provider", deployment.backup_provider),
            domain=request.data.get("domain", deployment.domain),
            build_command=request.data.get("build_command", deployment.build_command),
            output_directory=request.data.get("output_directory", deployment.output_directory),
            environment=request.data.get("environment", deployment.environment),
            status=DeploymentRun.Status.CONFIGURING,
            progress=8,
            created_by=request.user if request.user.is_authenticated else None,
        )
        _append_deployment_api_log(new_run, f"Redeploy record created for selected provider: {_provider_label(deployment.primary_provider)}.")
        if deployment.primary_provider not in UPLOAD_DEPLOYMENT_ADAPTERS:
            return _failed_deployment_response(new_run, _provider_adapter_error(deployment.primary_provider), http_status=status.HTTP_400_BAD_REQUEST)
        payload = {
            "domain": request.data.get("domain", deployment.domain),
            "environment": request.data.get("environment", deployment.environment),
        }
        preflight_error = _deployment_preflight_error(deployment.upload, payload, deployment.primary_provider)
        if preflight_error:
            return _failed_deployment_response(new_run, preflight_error, http_status=status.HTTP_400_BAD_REQUEST)
        new_run.status = DeploymentRun.Status.QUEUED
        new_run.progress = 12
        _append_deployment_api_log(new_run, "Redeploy passed preflight validation and was queued.", save=False)
        new_run.save(update_fields=["status", "progress", "logs"])
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


def _max_project_upload_bytes():
    return int(getattr(settings, "MAX_PROJECT_UPLOAD_BYTES", 5 * 1024 * 1024 * 1024))


def _positive_int(value, field_name, allow_zero=False):
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a number.") from exc
    if number < 0 or (number == 0 and not allow_zero):
        raise ValueError(f"{field_name} must be greater than zero.")
    return number


def _safe_upload_filename(value):
    raw = str(value or "project-upload.zip").replace("\\", "/").split("/")[-1]
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in raw).strip(".")
    return (cleaned or "project-upload.zip")[:180]


def _upload_session_root():
    media_root = Path(getattr(settings, "MEDIA_ROOT", Path(settings.BASE_DIR) / "media"))
    return media_root / "hosting_upload_sessions"


def _upload_session_dir(session):
    return _upload_session_root() / str(session.id)


def _get_upload_session(request):
    session_id = request.data.get("upload_id") or request.data.get("session_id") or request.query_params.get("upload_id") or request.query_params.get("session_id")
    if not session_id:
        return None
    try:
        session = ProjectUploadSession.objects.select_related("owner", "created_upload").get(id=session_id)
    except (ProjectUploadSession.DoesNotExist, ValueError):
        return None
    if session.owner_id and (not request.user.is_authenticated or session.owner_id != request.user.id):
        return None
    return session


def _upload_session_payload(session):
    missing = session.missing_chunks
    received = len(session.received_chunks or [])
    progress = round((received / max(1, session.total_chunks)) * 100, 2)
    return {
        "upload_id": str(session.id),
        "original_name": session.original_name,
        "source_type": session.source_type,
        "size_bytes": session.size_bytes,
        "chunk_size": session.chunk_size,
        "total_chunks": session.total_chunks,
        "received_chunks": sorted(session.received_chunks or []),
        "missing_chunks": missing,
        "progress": progress,
        "status": session.status,
        "created_upload": str(session.created_upload_id) if session.created_upload_id else None,
        "error_message": session.error_message,
        "expires_at": session.expires_at,
    }


def _complete_upload_session(session, request):
    temp_dir = Path(session.temp_dir or _upload_session_dir(session))
    if not temp_dir.exists():
        raise ValueError("Upload session storage is missing.")
    assembled_path = temp_dir / _safe_upload_filename(session.original_name)
    with assembled_path.open("wb") as destination:
        for index in range(session.total_chunks):
            chunk_path = temp_dir / f"{index:08d}.part"
            if not chunk_path.exists():
                raise ValueError(f"Missing chunk {index}.")
            with chunk_path.open("rb") as source:
                shutil.copyfileobj(source, destination)
    actual_size = assembled_path.stat().st_size
    if actual_size != session.size_bytes:
        raise ValueError(f"Upload size mismatch. Expected {session.size_bytes} bytes, received {actual_size} bytes.")
    if actual_size > _max_project_upload_bytes():
        raise ValueError(f"Project uploads are limited to {_max_project_upload_bytes() // (1024 * 1024)}MB.")
    with assembled_path.open("rb") as source:
        upload = ProjectUpload.objects.create(
            owner=session.owner if session.owner_id else request.user if request.user.is_authenticated else None,
            original_name=session.original_name,
            upload=File(source, name=session.original_name),
            size_bytes=actual_size,
        )
    session.created_upload = upload
    session.status = ProjectUploadSession.Status.COMPLETED
    session.error_message = ""
    session.save(update_fields=["created_upload", "status", "error_message", "updated_at"])
    shutil.rmtree(temp_dir, ignore_errors=True)
    return upload


def _normalize_upload_provider(value, allow_blank=False):
    provider = str(value or "").strip().lower().replace(" ", "_")
    if not provider and allow_blank:
        return ""
    return PROVIDER_ALIASES.get(provider, provider)


def _provider_adapter_error(provider):
    return {
        "detail": (
            f"{_provider_label(provider)} is not available for uploaded-package deployment in this router. "
            "No fallback deployment was queued."
        ),
        "provider": provider,
        "fallback_provider": None,
        "supported_upload_providers": sorted(UPLOAD_DEPLOYMENT_ADAPTERS),
        "required_action": f"Select one of {', '.join(sorted(UPLOAD_DEPLOYMENT_ADAPTERS))} or connect a real {_provider_label(provider)} deployment adapter.",
    }


def _failed_deployment_response(deployment, payload, http_status=status.HTTP_400_BAD_REQUEST):
    message = payload.get("detail") if isinstance(payload, dict) else str(payload)
    deployment.status = DeploymentRun.Status.FAILED
    deployment.progress = max(1, deployment.progress or 1)
    deployment.error_message = message
    deployment.completed_at = timezone.now()
    _append_deployment_api_log(deployment, message, level="error", save=False)
    deployment.save(update_fields=["status", "progress", "error_message", "completed_at", "logs"])
    data = DeploymentRunSerializer(deployment).data
    if isinstance(payload, dict):
        data.update(payload)
    else:
        data["detail"] = str(payload)
    return Response(data, status=http_status)


def _append_deployment_api_log(deployment, message, level="info", save=True):
    logs = list(deployment.logs or [])
    logs.append({"time": timezone.now().isoformat(), "level": level, "message": message})
    deployment.logs = logs
    if save:
        deployment.save(update_fields=["logs"])


def _deployment_preflight_error(upload, payload, provider):
    environment = payload.get("environment") or {}
    if not isinstance(environment, dict):
        return {
            "detail": "Environment variables must be submitted as an object.",
            "code": "invalid_environment",
            "provider": provider,
        }
    missing_env = _missing_environment_variables(upload, environment, provider)
    if missing_env:
        return {
            "detail": "Deployment blocked because required environment variables or provider secrets are missing.",
            "code": "missing_environment_variables",
            "provider": provider,
            "missing": missing_env,
            "fix_wizard": {
                "title": "Add missing deployment secrets",
                "fields": missing_env,
                "action": "Update project environment variables or provider credentials, then retry deployment.",
            },
        }
    domain = str(payload.get("domain") or "").strip().lower()
    if domain:
        domain_error = _domain_validation_error(domain)
        if domain_error:
            return {
                "detail": "Deployment blocked because the custom domain failed validation.",
                "code": "invalid_domain",
                "provider": provider,
                "domain": domain,
                "reason": domain_error,
            }
    return None


def _missing_environment_variables(upload, environment, provider):
    required = set()
    analysis = upload.analysis if isinstance(upload.analysis, dict) else {}
    required.update(name for name in analysis.get("environment_variables", []) if name)
    missing = [name for name in sorted(required) if not _secret_present(environment.get(name))]
    for accepted_names in PROVIDER_SECRET_REQUIREMENTS.get(provider, []):
        if not any(_secret_present(environment.get(name)) or _secret_present(getattr(settings, name, "")) for name in accepted_names):
            missing.append("/".join(accepted_names))
    return missing


def _secret_present(value):
    text = str(value or "").strip()
    if not text:
        return False
    lowered = text.lower()
    return lowered not in {"changeme", "change-me", "placeholder", "your-key", "your-secret", "todo"}


def _setting_first(*names):
    for name in names:
        value = getattr(settings, name, "")
        if str(value or "").strip():
            return str(value).strip()
    return ""


def _provider_response_payload(response):
    try:
        return response.json() if response.content else {}
    except ValueError:
        return {"detail": response.text}


def _provider_response_message(payload, response, fallback):
    if isinstance(payload, dict):
        return payload.get("message") or payload.get("error") or payload.get("detail") or response.text or fallback
    return response.text or fallback


def _azure_access_token_for_logs():
    missing = [name for name in ("AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "AZURE_TENANT_ID") if not _setting_first(name)]
    if missing:
        raise ValueError(f"Missing required Azure log setting(s): {', '.join(missing)}.")
    response = requests.post(
        f"https://login.microsoftonline.com/{_setting_first('AZURE_TENANT_ID')}/oauth2/v2.0/token",
        data={
            "client_id": _setting_first("AZURE_CLIENT_ID"),
            "client_secret": _setting_first("AZURE_CLIENT_SECRET"),
            "grant_type": "client_credentials",
            "scope": "https://management.azure.com/.default",
        },
        timeout=30,
    )
    payload = _provider_response_payload(response)
    if response.status_code >= 400:
        raise ValueError(_provider_response_message(payload, response, "Azure log token request failed."))
    token = payload.get("access_token") if isinstance(payload, dict) else ""
    if not token:
        raise ValueError("Azure log token response did not include access_token.")
    return token


def _domain_validation_error(domain):
    if not DOMAIN_RE.match(domain):
        return "Domain must be a fully qualified hostname with a valid public suffix."
    try:
        socket.getaddrinfo(domain, 443)
    except socket.gaierror as exc:
        return f"DNS lookup failed: {exc}."
    except OSError as exc:
        return f"DNS validation failed: {exc}."
    return ""


def _provider_label(provider):
    labels = {
        "aws": "AWS",
        "azure": "Azure",
        "gcp": "Google Cloud",
        "railway": "Railway",
        "render": "Render",
        "vercel": "Vercel",
        "netlify": "Netlify",
        "firebase": "Firebase",
        "fly": "Fly.io",
        "digitalocean": "DigitalOcean",
        "hostinger": "Hostinger",
        "cloudflare": "Cloudflare Pages",
        "github": "GitHub Deployments",
        "cpanel": "cPanel",
        "plesk": "Plesk",
    }
    return labels.get(provider, provider)


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


def _queue_task_safely(task, label):
    try:
        job = task.delay()
        return getattr(job, "id", ""), ""
    except Exception as exc:
        logger.warning(
            "Hosting refresh task could not be queued.",
            extra={"task_label": label, "error_cause": str(exc)},
        )
        return "", f"{label} could not be queued: {exc}"


def _invalidate_hosting_refresh_cache():
    patterns = ("vercel:*", "netlify:*", "hosting-dashboard:*", "hosting-overview:*")
    deleted = 0
    try:
        delete_pattern = getattr(cache, "delete_pattern", None)
        if callable(delete_pattern):
            for pattern in patterns:
                deleted += int(delete_pattern(pattern) or 0)
            return {"ok": True, "deleted": deleted, "patterns": list(patterns)}
        return {
            "ok": True,
            "deleted": 0,
            "patterns": [],
            "warning": "Configured cache backend does not support pattern invalidation.",
        }
    except Exception as exc:
        logger.warning(
            "Hosting refresh cache invalidation skipped.",
            extra={"error_cause": str(exc), "patterns": list(patterns)},
        )
        return {
            "ok": False,
            "deleted": 0,
            "patterns": list(patterns),
            "warning": f"Cache invalidation skipped: {exc}",
        }


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
    return "down" if str(text).lower() in {"offline", "down", "error", "disabled", "suspended", "maintenance"} else "running"
