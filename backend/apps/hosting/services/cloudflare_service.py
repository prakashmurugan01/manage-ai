import requests

from apps.hosting.models import HostedProject

from .base_service import BaseHostingService, ProviderConnectionError, UnsupportedProviderAction


class CloudflareHostingService(BaseHostingService):
    provider = "cloudflare"
    required_settings = ("CLOUDFLARE_API_TOKEN",)
    base_url = "https://api.cloudflare.com/client/v4"

    def provider_aliases(self):
        return ["cloudflare", "dns", HostedProject.Platform.CUSTOM]

    def get_projects(self):
        self.validate_connection()
        return self._request("GET", "/zones").get("result", [])

    def get_project_details(self, project_id):
        self.validate_connection()
        zone = self._request("GET", f"/zones/{project_id}").get("result", {})
        records = self._request("GET", f"/zones/{project_id}/dns_records").get("result", [])
        return {"zone": zone, "dns_records": records}

    def get_status(self, project_id):
        detail = self.get_project_details(project_id).get("zone", {})
        return {"state": detail.get("status", "unknown").title(), "server_status": detail.get("status", "unknown"), "project_status": detail.get("type", "zone")}

    def start_server(self, project_id):
        return self._set_paused(project_id, False)

    def stop_server(self, project_id):
        return self._set_paused(project_id, True)

    def restart_server(self, project_id):
        raise UnsupportedProviderAction("Cloudflare zones do not support restart; pause/unpause the zone or purge cache instead.")

    def redeploy(self, project_id):
        return self._request("POST", f"/zones/{project_id}/purge_cache", json={"purge_everything": True})

    def fetch_logs(self, project_id):
        return self._request("GET", f"/zones/{project_id}/dns_records").get("result", [])

    def _set_paused(self, zone_id, paused):
        return self._request("PATCH", f"/zones/{zone_id}", json={"paused": paused})

    def _request(self, method, path, json=None):
        response = requests.request(
            method,
            f"{self.base_url}{path}",
            headers={"Authorization": f"Bearer {self.setting('CLOUDFLARE_API_TOKEN')}", "Content-Type": "application/json"},
            json=json,
            timeout=20,
        )
        try:
            payload = response.json()
        except ValueError:
            payload = {"errors": [{"message": response.text}]}
        if response.status_code >= 400 or payload.get("success") is False:
            message = (payload.get("errors") or [{}])[0].get("message") or "Cloudflare API request failed."
            raise ProviderConnectionError(message, code="invalid_credentials", status_code=response.status_code or 502, payload=payload)
        return payload
