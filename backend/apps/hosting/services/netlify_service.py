from apps.hosting.models import HostingLink
from apps.hosting.netlify import NetlifyApiError, NetlifyClient, get_netlify_status
from apps.hosting.providers import ensure_default_providers, sync_netlify_sites

from .base_service import BaseHostingService, ProviderConnectionError, UnsupportedProviderAction


class NetlifyHostingService(BaseHostingService):
    provider = HostingLink.Provider.NETLIFY
    required_settings = ("NETLIFY_API_TOKEN",)

    def get_projects(self):
        self.validate_connection()
        try:
            ensure_default_providers()
            sync_netlify_sites()
            return get_netlify_status(force=True).get("sites", [])
        except NetlifyApiError as exc:
            raise ProviderConnectionError(str(exc), code="invalid_credentials", status_code=exc.status_code or 502, payload=exc.payload) from exc

    def redeploy(self, project_id):
        self.validate_connection()
        link = self._project(project_id).hosting_links.filter(provider=self.provider).first()
        if not link or not link.external_id:
            raise ProviderConnectionError("Netlify site is not linked to this project.", code="not_found", status_code=404)
        try:
            return {"detail": "Redeploy requested.", "payload": NetlifyClient().trigger_build(link.external_id)}
        except NetlifyApiError as exc:
            raise ProviderConnectionError(str(exc), code="invalid_credentials", status_code=exc.status_code or 502, payload=exc.payload) from exc

    def fetch_logs(self, project_id):
        self.validate_connection()
        link = self._project(project_id).hosting_links.filter(provider=self.provider).first()
        try:
            deploys = NetlifyClient().list_deploys(limit=30)
        except NetlifyApiError as exc:
            raise ProviderConnectionError(str(exc), code="invalid_credentials", status_code=exc.status_code or 502, payload=exc.payload) from exc
        if link and link.external_id:
            deploys = [item for item in deploys if item.get("site_id") == link.external_id]
        return deploys

    def start_server(self, project_id):
        raise UnsupportedProviderAction("Netlify does not expose start/stop controls; use Redeploy or disable the dashboard link.")

    def stop_server(self, project_id):
        raise UnsupportedProviderAction("Netlify does not expose start/stop controls; use provider-side deploy controls.")
