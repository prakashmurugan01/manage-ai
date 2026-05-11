from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.accounts.serializers import TeamSerializer, UserSerializer
from apps.core.permissions import Roles, has_role, is_admin_level

from .models import (
    ApprovalRequest,
    ApprovalStage,
    ApprovalTemplate,
    BusinessHours,
    Holiday,
    SLAPolicy,
    ServiceItem,
    Ticket,
    TicketActivity,
    TicketAttachment,
    TicketComment,
    WorkflowExecution,
    WorkflowTemplate,
)

User = get_user_model()


class ServiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceItem
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class TicketAttachmentSerializer(serializers.ModelSerializer):
    uploaded_by_detail = UserSerializer(source="uploaded_by", read_only=True)

    class Meta:
        model = TicketAttachment
        fields = ("id", "ticket", "comment", "file", "caption", "uploaded_by", "uploaded_by_detail", "file_size", "created_at", "updated_at")
        read_only_fields = ("uploaded_by", "file_size", "created_at", "updated_at")


class TicketCommentSerializer(serializers.ModelSerializer):
    author_detail = UserSerializer(source="author", read_only=True)
    mentions_detail = UserSerializer(source="mentions", many=True, read_only=True)
    attachments = TicketAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = TicketComment
        fields = ("id", "ticket", "author", "author_detail", "body", "is_internal", "mentions", "mentions_detail", "attachments", "metadata", "created_at", "updated_at")
        read_only_fields = ("author", "created_at", "updated_at")

    def validate(self, attrs):
        request = self.context.get("request")
        if request and has_role(request.user, Roles.CLIENT):
            attrs["is_internal"] = False
        return attrs


class TicketActivitySerializer(serializers.ModelSerializer):
    actor_detail = UserSerializer(source="actor", read_only=True)

    class Meta:
        model = TicketActivity
        fields = ("id", "ticket", "action", "field_changed", "old_value", "new_value", "actor", "actor_detail", "metadata", "timestamp")
        read_only_fields = fields


class TicketSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    requester_detail = UserSerializer(source="requester", read_only=True)
    raised_by_detail = UserSerializer(source="raised_by", read_only=True)
    assigned_to_detail = UserSerializer(source="assigned_to", read_only=True)
    assigned_group_detail = TeamSerializer(source="assigned_group", read_only=True)
    service_item_detail = ServiceItemSerializer(source="service_item", read_only=True)
    comments = TicketCommentSerializer(many=True, read_only=True)
    attachments = TicketAttachmentSerializer(many=True, read_only=True)
    activities = TicketActivitySerializer(many=True, read_only=True)
    child_ticket_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Ticket
        fields = (
            "id",
            "ticket_id",
            "type",
            "project",
            "project_name",
            "organization",
            "organization_name",
            "title",
            "description",
            "screenshot",
            "priority",
            "severity",
            "impact",
            "urgency",
            "status",
            "category",
            "subcategory",
            "service_item",
            "service_item_detail",
            "requester",
            "requester_detail",
            "raised_by",
            "raised_by_detail",
            "assigned_to",
            "assigned_to_detail",
            "assigned_group",
            "assigned_group_detail",
            "source",
            "auto_assigned",
            "assignment_reason",
            "first_response_at",
            "resolved_at",
            "closed_at",
            "sla_due_at",
            "sla_breached",
            "sla_paused_at",
            "sla_pause_reason",
            "parent_ticket",
            "related_tickets",
            "tags",
            "custom_fields",
            "attachments",
            "comments",
            "activities",
            "child_ticket_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "ticket_id",
            "requester",
            "raised_by",
            "auto_assigned",
            "assignment_reason",
            "first_response_at",
            "resolved_at",
            "closed_at",
            "sla_due_at",
            "sla_breached",
            "created_at",
            "updated_at",
        )

    def validate_assigned_to(self, value):
        if value and value.role not in {User.Role.DEVELOPER, User.Role.ADMIN, User.Role.SUPER_ADMIN}:
            raise serializers.ValidationError("Tickets can only be assigned to developers or admins.")
        return value

    def validate(self, attrs):
        request = self.context.get("request")
        if not request:
            return attrs

        user = request.user
        project = attrs.get("project", getattr(self.instance, "project", None))
        if project:
            if has_role(user, Roles.CLIENT) and project.client_id != user.id:
                raise serializers.ValidationError({"project": "Clients can only raise tickets for assigned projects."})
            if has_role(user, Roles.DEVELOPER) and not project.developers.filter(id=user.id).exists():
                raise serializers.ValidationError({"project": "Developers can only raise tickets for assigned projects."})
            if has_role(user, Roles.ADMIN) and not (
                project.owner_id == user.id or project.created_by_id == user.id or project.admins.filter(id=user.id).exists()
            ):
                raise serializers.ValidationError({"project": "Admins can only raise tickets for managed projects."})

        if request.method == "POST":
            attrs["priority"] = Ticket.normalize_priority(attrs.get("priority", Ticket.Priority.P3))
            if has_role(user, Roles.CLIENT):
                attrs["source"] = Ticket.Source.CLIENT
            elif has_role(user, Roles.DEVELOPER):
                attrs["source"] = Ticket.Source.DEVELOPER
            elif is_admin_level(user):
                attrs["source"] = attrs.get("source", Ticket.Source.ADMIN)
            return attrs

        if has_role(user, Roles.DEVELOPER):
            allowed = {"status", "priority", "assigned_to", "assigned_group", "tags", "custom_fields"}
            invalid = set(attrs) - allowed
            if invalid:
                raise serializers.ValidationError("Developers can only update ticket workflow, assignment, tags, and custom fields.")
        if has_role(user, Roles.CLIENT):
            allowed = {"status"}
            invalid = set(attrs) - allowed
            if invalid:
                raise serializers.ValidationError("Clients can only update ticket status.")
        return attrs


class SLAPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = SLAPolicy
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class BusinessHoursSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessHours
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")

    def validate(self, attrs):
        if attrs["start_time"] >= attrs["end_time"]:
            raise serializers.ValidationError("Business hours start_time must be before end_time.")
        if not 0 <= attrs["day_of_week"] <= 6:
            raise serializers.ValidationError("day_of_week must be between 0 and 6.")
        return attrs


class HolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Holiday
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class WorkflowTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowTemplate
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")

    def validate_actions(self, value):
        allowed = {"assign_ticket", "change_status", "send_notification", "add_comment", "create_child_ticket", "trigger_webhook", "ai_classify"}
        if not isinstance(value, list):
            raise serializers.ValidationError("Actions must be an ordered list.")
        for action in value:
            if action.get("type") not in allowed:
                raise serializers.ValidationError(f"Unsupported action type: {action.get('type')}")
        return value


class WorkflowExecutionSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source="template.name", read_only=True)

    class Meta:
        model = WorkflowExecution
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at", "started_at", "completed_at")


class ApprovalTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApprovalTemplate
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class ApprovalStageSerializer(serializers.ModelSerializer):
    approver_detail = UserSerializer(source="approver", read_only=True)
    decided_by_detail = UserSerializer(source="decided_by", read_only=True)

    class Meta:
        model = ApprovalStage
        fields = "__all__"
        read_only_fields = ("decided_by", "decided_at", "created_at", "updated_at")


class ApprovalRequestSerializer(serializers.ModelSerializer):
    stages = ApprovalStageSerializer(many=True, read_only=True)
    requested_by_detail = UserSerializer(source="requested_by", read_only=True)

    class Meta:
        model = ApprovalRequest
        fields = "__all__"
        read_only_fields = ("requested_by", "status", "current_stage_order", "completed_at", "created_at", "updated_at")


class ApprovalDecisionSerializer(serializers.Serializer):
    comments = serializers.CharField(required=False, allow_blank=True)
