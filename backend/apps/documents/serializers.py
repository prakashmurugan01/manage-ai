from rest_framework import serializers

from apps.accounts.serializers import UserSerializer
from apps.core.permissions import Roles, has_role
from apps.projects.models import Project

from .models import Document

MAX_PROJECT_ZIP_BYTES = 5 * 1024 * 1024 * 1024


class DocumentSerializer(serializers.ModelSerializer):
    uploaded_by_detail = UserSerializer(source="uploaded_by", read_only=True)
    reviewed_by_detail = UserSerializer(source="reviewed_by", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)
    download_url = serializers.SerializerMethodField()
    preview_url = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = (
            "id",
            "project",
            "project_name",
            "uploaded_by",
            "uploaded_by_detail",
            "title",
            "description",
            "file",
            "download_url",
            "preview_url",
            "category",
            "visibility",
            "version",
            "file_size",
            "extension",
            "review_status",
            "review_note",
            "reviewed_by",
            "reviewed_by_detail",
            "reviewed_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("uploaded_by", "file_size", "extension", "reviewed_by", "reviewed_at", "created_at", "updated_at")

    def get_download_url(self, obj):
        request = self.context.get("request")
        if not request:
            return None
        return request.build_absolute_uri(f"/api/documents/{obj.pk}/download/")

    def get_preview_url(self, obj):
        request = self.context.get("request")
        if not request:
            return None
        return request.build_absolute_uri(f"/api/documents/{obj.pk}/preview/")

    def validate(self, attrs):
        request = self.context.get("request")
        project = attrs.get("project", getattr(self.instance, "project", None))
        uploaded_file = attrs.get("file", getattr(self.instance, "file", None))
        if uploaded_file and getattr(uploaded_file, "size", 0) > MAX_PROJECT_ZIP_BYTES:
            raise serializers.ValidationError({"file": "Project ZIP uploads are limited to 5GB."})
        if request and has_role(request.user, Roles.DEVELOPER):
            if project and not (project.developers.filter(id=request.user.id).exists() or project.teams.filter(members=request.user).exists()):
                raise serializers.ValidationError({"project": "Developers can only upload files for assigned projects."})
            if project and project.approval_status != Project.ApprovalStatus.APPROVED:
                raise serializers.ValidationError({"file": "Admin approval is required before developers can upload project files to server storage."})
            attrs["visibility"] = Document.Visibility.INTERNAL
            attrs["review_status"] = Document.ReviewStatus.PENDING
        return attrs


class DocumentReviewSerializer(serializers.Serializer):
    review_status = serializers.ChoiceField(choices=Document.ReviewStatus.choices)
    review_note = serializers.CharField(required=False, allow_blank=True)
