from abc import ABC, abstractmethod

from django.utils import timezone

from apps.hosting.models import HostedProject, HostingLink


class ProviderConnectionError(Exception):
    def __init__(self, message="API NOT CONNECTED", code="api_not_connected", status_code=503, payload=None):
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.payload = payload or {}


class UnsupportedProviderAction(ProviderConnectionError):
    def __init__(self, message="This provider does not support this server action through its public API."):
        super().__init__(message, code="unsupported_action", status_code=409)


class BaseHostingService(ABC):
    provider = ""
    required_settings = ()

    def __init__(self, user=None):
        self.user = user

    def validate_connection(self):
        missing = [name for name in self.required_settings if not self.setting(name)]
        if missing:
            raise ProviderConnectionError(
                "API NOT CONNECTED",
                code="missing_credentials",
                payload={"missing": missing, "message": "Invalid Credentials"},
            )

    def setting(self, name, default=""):
        from django.conf import settings

        return getattr(settings, name, default)

    @abstractmethod
    def get_projects(self):
        raise NotImplementedError

    def get_project_details(self, project_id):
        project = self._project(project_id)
        return self.serialize_project(project)

    def get_status(self, project_id):
        project = self._project(project_id)
        return self.status_payload(project)

    def start_server(self, project_id):
        return self._toggle_first_link(project_id, True, "Starting")

    def stop_server(self, project_id):
        return self._toggle_first_link(project_id, False, "Stopping")

    def restart_server(self, project_id):
        self.stop_server(project_id)
        return self.start_server(project_id)

    def redeploy(self, project_id):
        raise UnsupportedProviderAction()

    def fetch_logs(self, project_id):
        project = self._project(project_id)
        return [
            {
                "level": "info",
                "title": item.get_event_type_display(),
                "message": item.notes or item.event_type,
                "created_at": item.created_at,
            }
            for item in project.lifecycle.order_by("-created_at")[:50]
        ]

    def local_projects(self):
        return HostedProject.objects.filter(hosting_platform__in=self.provider_aliases()).order_by("name")

    def local_links(self):
        return HostingLink.objects.select_related("project").filter(provider__in=self.provider_aliases()).order_by("project__name", "priority")

    def provider_aliases(self):
        return [self.provider]

    def serialize_project(self, project):
        links = [self.serialize_link(link) for link in project.hosting_links.filter(provider__in=self.provider_aliases())]
        return {
            "id": project.id,
            "name": project.name,
            "provider": project.hosting_platform,
            "domain": project.domain,
            "live_url": project.deploy_url,
            "status": self.status_payload(project),
            "disabled": not project.link_is_active or project.server_status == HostedProject.ServerStatus.OFFLINE,
            "links": links,
            "last_checked_at": project.last_checked_at,
        }

    def serialize_link(self, link):
        return {
            "id": link.id,
            "provider": link.provider,
            "project_id": link.project_id,
            "name": link.label or link.project.name,
            "external_id": link.external_id,
            "live_url": link.url,
            "domain": link.domain,
            "status": "Running" if link.status == HostingLink.Status.ON else "Offline" if link.status == HostingLink.Status.OFF else link.status.title(),
            "health": link.health_status,
            "is_enabled": link.is_enabled,
            "is_active": link.is_active,
            "uptime": float(link.uptime_percentage or 0),
            "response_time_ms": link.response_time_ms,
            "last_checked_at": link.last_checked_at,
            "metadata": link.metadata,
        }

    def status_payload(self, project):
        if not project.link_is_active or project.server_status == HostedProject.ServerStatus.OFFLINE:
            state = "Offline"
        elif project.server_status == HostedProject.ServerStatus.SLOW:
            state = "Degraded"
        elif project.status in {HostedProject.Status.SUSPENDED, HostedProject.Status.MAINTENANCE}:
            state = "Offline"
        else:
            state = "Running"
        return {
            "state": state,
            "server_status": project.server_status,
            "project_status": project.status,
            "uptime": float(project.uptime_percentage or 0),
            "response_time_ms": project.response_time_ms,
            "last_checked_at": project.last_checked_at,
        }

    def _project(self, project_id):
        try:
            return HostedProject.objects.prefetch_related("hosting_links", "lifecycle").get(id=project_id)
        except HostedProject.DoesNotExist as exc:
            raise ProviderConnectionError("Project not found.", code="not_found", status_code=404) from exc

    def _toggle_first_link(self, project_id, enabled, pending_state):
        from apps.hosting.providers import ProviderError, toggle_hosting_link

        project = self._project(project_id)
        link = project.hosting_links.filter(provider__in=self.provider_aliases()).order_by("priority").first()
        if not link:
            project.link_is_active = enabled
            project.server_status = HostedProject.ServerStatus.UNKNOWN if enabled else HostedProject.ServerStatus.OFFLINE
            project.status = HostedProject.Status.LIVE if enabled else HostedProject.Status.SUSPENDED
            project.save(update_fields=["link_is_active", "server_status", "status"])
            return {"detail": f"{pending_state} requested.", "project": self.serialize_project(project)}
        try:
            toggle_hosting_link(link, enabled, user=self.user)
        except ProviderError as exc:
            raise ProviderConnectionError(str(exc), code="provider_error", status_code=502) from exc
        project.refresh_from_db()
        project.link_is_active = enabled
        project.server_status = HostedProject.ServerStatus.UNKNOWN if enabled else HostedProject.ServerStatus.OFFLINE
        project.status = HostedProject.Status.LIVE if enabled else HostedProject.Status.SUSPENDED
        project.last_checked_at = timezone.now()
        project.save(update_fields=["link_is_active", "server_status", "status", "last_checked_at"])
        return {"detail": f"{pending_state} requested.", "project": self.serialize_project(project)}
