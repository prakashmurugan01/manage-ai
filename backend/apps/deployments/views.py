from django.db.models import Q
from rest_framework import decorators, filters, viewsets
from rest_framework.response import Response

from apps.core.mixins import AuditModelViewSetMixin
from apps.core.permissions import IsAdminLevel, Roles, has_role, is_admin_level
from apps.documents.models import Document

from .models import DeploymentControl
from .serializers import DeploymentControlSerializer, DeploymentToggleSerializer


class DeploymentControlViewSet(AuditModelViewSetMixin, viewsets.ModelViewSet):
    serializer_class = DeploymentControlSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["project__name", "version", "notes"]
    ordering_fields = ["updated_at", "last_deployed_at", "status"]
    ordering = ["project__name"]
    audit_entity = "DeploymentControl"

    def get_permissions(self):
        if self.action in {"toggle", "create", "update", "partial_update", "destroy"}:
            return [IsAdminLevel()]
        from rest_framework.permissions import IsAuthenticated

        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        qs = DeploymentControl.objects.select_related("project", "toggled_by").prefetch_related("history")
        if getattr(user, "company_id", None):
            qs = qs.filter(Q(project__company_id=user.company_id) | Q(project__company__isnull=True))
        if has_role(user, Roles.SUPER_ADMIN):
            scoped = qs
        if has_role(user, Roles.ADMIN):
            scoped = qs.filter(Q(project__owner=user) | Q(project__admins=user) | Q(project__created_by=user)).distinct()
        elif has_role(user, Roles.DEVELOPER):
            scoped = qs.filter(project__developers=user).distinct()
        elif has_role(user, Roles.CLIENT):
            scoped = qs.filter(project__client=user).distinct()
        elif is_admin_level(user):
            scoped = qs
        else:
            scoped = qs.none()

        project_id = self.request.query_params.get("project")
        if project_id:
            scoped = scoped.filter(project_id=project_id)
        return scoped

    @decorators.action(detail=True, methods=["post"])
    def toggle(self, request, pk=None):
        deployment = self.get_object()
        serializer = DeploymentToggleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data["is_enabled"] and deployment.project.documents.exclude(review_status=Document.ReviewStatus.APPROVED).exists():
            return Response({"detail": "All project files must be approved before deployment can be enabled."}, status=400)
        deployment.version = serializer.validated_data.get("version", deployment.version)
        deployment.source_branch = serializer.validated_data.get("source_branch", deployment.source_branch)
        deployment.commit_sha = serializer.validated_data.get("commit_sha", deployment.commit_sha)
        deployment.notes = serializer.validated_data.get("notes", deployment.notes)
        deployment.set_enabled(serializer.validated_data["is_enabled"], request.user)
        from apps.audit.services import audit_event

        audit_event(request, "DEPLOYMENT_TOGGLE", "DeploymentControl", deployment.pk, {"is_enabled": deployment.is_enabled})
        return Response(DeploymentControlSerializer(deployment, context={"request": request}).data)
