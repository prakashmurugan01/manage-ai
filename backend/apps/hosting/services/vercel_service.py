from apps.hosting.models import HostingLink, VercelProject
from apps.hosting.vercel import VercelApiError, VercelClient, sync_project_deployments, sync_vercel_projects

from .base_service import BaseHostingService, ProviderConnectionError


class VercelHostingService(BaseHostingService):
    provider = HostingLink.Provider.VERCEL
    required_settings = ("VERCEL_API_TOKEN",)

    def get_projects(self):
        self.validate_connection()
        try:
            sync_vercel_projects()
        except VercelApiError as exc:
            raise ProviderConnectionError(str(exc), code="invalid_credentials", status_code=exc.status_code or 502, payload=exc.payload) from exc
        return [self.serialize_project(project.hosted_project) for project in VercelProject.objects.select_related("hosted_project").filter(hosted_project__isnull=False)]

    def redeploy(self, project_id):
        self.validate_connection()
        project = VercelProject.objects.filter(hosted_project_id=project_id).first()
        if not project or not project.latest_deployment_id:
            raise ProviderConnectionError("Vercel deployment is not linked to this project.", code="not_found", status_code=404)
        try:
            payload = VercelClient(team_id=project.team_id).redeploy(project.latest_deployment_id)
            sync_project_deployments(project)
            return {"detail": "Redeploy requested.", "payload": payload}
        except VercelApiError as exc:
            raise ProviderConnectionError(str(exc), code="invalid_credentials", status_code=exc.status_code or 502, payload=exc.payload) from exc

    def fetch_logs(self, project_id):
        self.validate_connection()
        project = VercelProject.objects.filter(hosted_project_id=project_id).first()
        if not project or not project.latest_deployment_id:
            return []
        try:
            return VercelClient(team_id=project.team_id).deployment_events(project.latest_deployment_id)
        except VercelApiError as exc:
            raise ProviderConnectionError(str(exc), code="invalid_credentials", status_code=exc.status_code or 502, payload=exc.payload) from exc
