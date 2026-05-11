from django.db.models import Q
from django.http import FileResponse
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework import decorators, filters, parsers, status, viewsets
from rest_framework.response import Response

from apps.core.mixins import AuditModelViewSetMixin
from apps.core.permissions import DocumentRBACPermission, Roles, has_role, is_admin_level

from .models import Document
from apps.notifications.services import notify_user

from .serializers import DocumentReviewSerializer, DocumentSerializer

User = get_user_model()


class DocumentViewSet(AuditModelViewSetMixin, viewsets.ModelViewSet):
    serializer_class = DocumentSerializer
    permission_classes = [DocumentRBACPermission]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "description", "category", "project__name"]
    ordering_fields = ["updated_at", "created_at", "title", "file_size"]
    ordering = ["-updated_at"]
    audit_entity = "Document"

    def get_queryset(self):
        user = self.request.user
        qs = Document.objects.select_related("project", "uploaded_by", "project__client")
        project_id = self.request.query_params.get("project")
        visibility = self.request.query_params.get("visibility")
        if project_id:
            qs = qs.filter(project_id=project_id)
        if visibility:
            qs = qs.filter(visibility=visibility)
        if getattr(user, "company_id", None):
            qs = qs.filter(Q(project__company_id=user.company_id) | Q(project__company__isnull=True))
        if has_role(user, Roles.SUPER_ADMIN):
            return qs
        if has_role(user, Roles.ADMIN):
            return qs.filter(Q(project__owner=user) | Q(project__admins=user) | Q(project__created_by=user)).distinct()
        if has_role(user, Roles.DEVELOPER):
            return qs.filter(Q(project__developers=user) | Q(project__teams__members=user), visibility=Document.Visibility.INTERNAL).distinct()
        if has_role(user, Roles.CLIENT):
            return qs.filter(project__client=user, visibility__in=[Document.Visibility.CLIENT, Document.Visibility.PUBLIC]).distinct()
        if is_admin_level(user):
            return qs
        return qs.none()

    def perform_create(self, serializer):
        document = serializer.save(uploaded_by=self.request.user)
        recipients = {document.project.owner, document.project.created_by, *document.project.admins.all(), *User.objects.filter(role=User.Role.SUPER_ADMIN)}
        for recipient in recipients:
            if recipient and recipient.id != self.request.user.id:
                notify_user(
                    recipient=recipient,
                    sender=self.request.user,
                    title="Project file uploaded",
                    message=f"{document.title} was uploaded for {document.project.name}.",
                    type="FILE",
                    project=document.project,
                )

    @decorators.action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        document = self.get_object()
        if not is_admin_level(request.user) and document.review_status != Document.ReviewStatus.APPROVED:
            return Response({"detail": "This file must be approved by Admin before download."}, status=status.HTTP_403_FORBIDDEN)
        return FileResponse(document.file.open("rb"), as_attachment=True, filename=document.file.name.split("/")[-1])

    @decorators.action(detail=True, methods=["get"])
    def preview(self, request, pk=None):
        document = self.get_object()
        if not is_admin_level(request.user) and document.review_status != Document.ReviewStatus.APPROVED:
            return Response({"detail": "This file must be approved by Admin before preview."}, status=status.HTTP_403_FORBIDDEN)
        return FileResponse(document.file.open("rb"), as_attachment=False, filename=document.file.name.split("/")[-1])

    @decorators.action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        if not is_admin_level(request.user):
            return Response({"detail": "Only Admin and Super Admin can review project files."}, status=status.HTTP_403_FORBIDDEN)
        document = self.get_object()
        serializer = DocumentReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document.review_status = serializer.validated_data["review_status"]
        document.review_note = serializer.validated_data.get("review_note", "")
        document.reviewed_by = request.user
        document.reviewed_at = timezone.now()
        document.save(update_fields=["review_status", "review_note", "reviewed_by", "reviewed_at", "updated_at"])
        if document.uploaded_by and document.uploaded_by_id != request.user.id:
            notify_user(
                recipient=document.uploaded_by,
                sender=request.user,
                title="Project file reviewed",
                message=f"{document.title} is now {document.get_review_status_display()}.",
                type="FILE" if document.review_status == Document.ReviewStatus.APPROVED else "ALERT",
                project=document.project,
            )
        return Response(DocumentSerializer(document, context={"request": request}).data)
