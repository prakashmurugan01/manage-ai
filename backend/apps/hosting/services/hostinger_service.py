import requests

from apps.hosting.models import HostedProject, HostingLink
from apps.hosting.providers import ensure_default_providers, sync_hostinger_virtual_machines

from .base_service import BaseHostingService, ProviderConnectionError


class HostingerHostingService(BaseHostingService):
    provider = HostingLink.Provider.HOSTINGER
    required_settings = ("HOSTINGER_API_TOKEN",)
    base_url = "https://developers.hostinger.com/api/vps/v1"

    def get_projects(self):
        self.validate_connection()
        try:
            ensure_default_providers()
            sync_hostinger_virtual_machines()
        except ProviderConnectionError:
            raise
        except Exception as exc:
            raise ProviderConnectionError(str(exc), code="hostinger_api_error", status_code=502) from exc
        return [self.serialize_project(project) for project in self.local_projects()]

    def start_server(self, project_id):
        return self._vm_action(project_id, "start")

    def stop_server(self, project_id):
        return self._vm_action(project_id, "stop")

    def restart_server(self, project_id):
        return self._vm_action(project_id, "restart")

    def fetch_logs(self, project_id):
        project = self._project(project_id)
        link = project.hosting_links.filter(provider=self.provider).first()
        if not link or not link.external_id:
            return super().fetch_logs(project_id)
        return self._request("GET", f"/virtual-machines/{link.external_id}/actions")

    def _vm_action(self, project_id, action):
        self.validate_connection()
        project = self._project(project_id)
        link = project.hosting_links.filter(provider=self.provider).first()
        if not link or not link.external_id:
            raise ProviderConnectionError("Hostinger VPS is not linked to this project.", code="not_found", status_code=404)
        payload = self._request("POST", f"/virtual-machines/{link.external_id}/{action}")
        if action == "stop":
            project.link_is_active = False
            project.server_status = HostedProject.ServerStatus.OFFLINE
            project.status = HostedProject.Status.DISABLED
            link.status = HostingLink.Status.OFF
            link.health_status = HostingLink.Health.DOWN
        else:
            project.link_is_active = True
            project.server_status = HostedProject.ServerStatus.UNKNOWN
            project.status = HostedProject.Status.LIVE
            link.status = HostingLink.Status.ON
            link.health_status = HostingLink.Health.UNKNOWN
        project.save(update_fields=["link_is_active", "server_status", "status"])
        link.save(update_fields=["status", "health_status", "updated_at"])
        return {"detail": f"Hostinger {action} requested.", "payload": payload, "project": self.serialize_project(project)}

    def _request(self, method, path):
        response = requests.request(
            method,
            f"{self.base_url}{path}",
            headers={"Authorization": f"Bearer {self.setting('HOSTINGER_API_TOKEN')}", "Accept": "application/json"},
            timeout=20,
        )
        try:
            payload = response.json()
        except ValueError:
            payload = {"message": response.text}
        if response.status_code >= 400:
            message = payload.get("message") or payload.get("error") or "Hostinger API request failed."
            raise ProviderConnectionError(message, code="invalid_credentials", status_code=response.status_code or 502, payload=payload)
        return payload
