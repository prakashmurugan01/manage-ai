from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import decorators, filters, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import AuditModelViewSetMixin
from apps.core.permissions import IsAdminLevel, Roles, has_role, is_admin_level
from apps.notifications.services import notify_user

from .models import (
    ApprovalRequest,
    ApprovalStage,
    ApprovalTemplate,
    BusinessHours,
    Holiday,
    SLAPolicy,
    ServiceItem,
    Ticket,
    TicketAttachment,
    TicketComment,
    WorkflowExecution,
    WorkflowTemplate,
)
from .serializers import (
    ApprovalDecisionSerializer,
    ApprovalRequestSerializer,
    ApprovalStageSerializer,
    ApprovalTemplateSerializer,
    BusinessHoursSerializer,
    HolidaySerializer,
    SLAPolicySerializer,
    ServiceItemSerializer,
    TicketAttachmentSerializer,
    TicketCommentSerializer,
    TicketSerializer,
    WorkflowExecutionSerializer,
    WorkflowTemplateSerializer,
)
from .services import create_approval_request, record_activity

User = get_user_model()


class OrganizationScopedAdminMixin:
    permission_classes = [IsAuthenticated, IsAdminLevel]

    def perform_create(self, serializer):
        organization = serializer.validated_data.get("organization") or getattr(self.request.user, "company", None)
        serializer.save(organization=organization)


class TicketViewSet(AuditModelViewSetMixin, viewsets.ModelViewSet):
    serializer_class = TicketSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["ticket_id", "title", "description", "project__name", "requester__email", "assigned_to__email", "comments__body"]
    ordering_fields = ["updated_at", "created_at", "priority", "status", "sla_due_at"]
    ordering = ["-updated_at"]
    audit_entity = "Ticket"

    def get_queryset(self):
        user = self.request.user
        qs = (
            Ticket.objects.select_related("project", "organization", "requester", "raised_by", "assigned_to", "assigned_group", "service_item", "project__client")
            .prefetch_related("comments", "attachments", "activities", "related_tickets")
            .annotate(child_ticket_count=Count("child_tickets", distinct=True))
        )
        project_id = self.request.query_params.get("project")
        status_value = self.request.query_params.get("status")
        priority = self.request.query_params.get("priority")
        ticket_type = self.request.query_params.get("type")
        assignee = self.request.query_params.get("assigned_to") or self.request.query_params.get("assignee")
        category = self.request.query_params.get("category")
        sla_status = self.request.query_params.get("sla_status")
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")

        if project_id:
            qs = qs.filter(project_id=project_id)
        if status_value:
            qs = qs.filter(status=status_value)
        if priority:
            qs = qs.filter(priority=Ticket.normalize_priority(priority))
        if ticket_type:
            qs = qs.filter(type=ticket_type)
        if assignee:
            qs = qs.filter(assigned_to_id=assignee)
        if category:
            qs = qs.filter(category__iexact=category)
        if sla_status == "breached":
            qs = qs.filter(sla_breached=True)
        if sla_status == "at_risk":
            qs = qs.filter(sla_breached=False, sla_due_at__lte=timezone.now() + timedelta(hours=1))
        if sla_status == "healthy":
            qs = qs.filter(Q(sla_due_at__gt=timezone.now() + timedelta(hours=1)) | Q(sla_due_at__isnull=True), sla_breached=False)
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        query = self.request.query_params.get("q")
        if query:
            if connection.vendor == "postgresql":
                from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector

                vector = SearchVector("title", weight="A") + SearchVector("description", weight="B") + SearchVector("comments__body", weight="C")
                search_query = SearchQuery(query)
                qs = qs.annotate(rank=SearchRank(vector, search_query)).filter(rank__gte=0.05).order_by("-rank", "-updated_at")
            else:
                qs = qs.filter(Q(title__icontains=query) | Q(description__icontains=query) | Q(comments__body__icontains=query)).distinct()

        ordering = self.request.query_params.get("ordering")
        if ordering == "newest":
            qs = qs.order_by("-created_at")
        elif ordering == "oldest":
            qs = qs.order_by("created_at")
        elif ordering == "SLA_due":
            qs = qs.order_by("sla_due_at")
        elif ordering == "priority":
            qs = qs.order_by("priority", "sla_due_at")

        if getattr(user, "company_id", None):
            qs = qs.filter(Q(organization_id=user.company_id) | Q(organization__isnull=True))

        if has_role(user, Roles.SUPER_ADMIN):
            return qs.distinct()
        if has_role(user, Roles.ADMIN):
            return qs.filter(Q(project__owner=user) | Q(project__admins=user) | Q(project__created_by=user)).distinct()
        if has_role(user, Roles.DEVELOPER):
            return qs.filter(Q(assigned_to=user) | Q(assigned_group__members=user) | Q(project__developers=user) | Q(project__teams__members=user) | Q(requester=user) | Q(raised_by=user)).distinct()
        if has_role(user, Roles.CLIENT):
            return qs.filter(Q(project__client=user) | Q(requester=user) | Q(raised_by=user)).distinct()
        if is_admin_level(user):
            return qs.distinct()
        return qs.none()

    def perform_create(self, serializer):
        project = serializer.validated_data.get("project")
        assigned_to = serializer.validated_data.get("assigned_to")
        auto_assigned = False
        assignment_reason = ""
        if not assigned_to and project:
            assigned_to = (
                project.developers.annotate(
                    active_ticket_count=Count(
                        "assigned_tickets",
                        filter=~Q(assigned_tickets__status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED]),
                    )
                )
                .order_by("active_ticket_count", "id")
                .first()
            )
            auto_assigned = bool(assigned_to)
            if assigned_to:
                assignment_reason = f"Auto-assigned to {assigned_to.get_full_name() or assigned_to.email} from the {project.name} team."
        ticket = serializer.save(
            requester=self.request.user,
            raised_by=self.request.user,
            organization=getattr(project, "company", None),
            assigned_to=assigned_to,
            auto_assigned=auto_assigned,
            assignment_reason=assignment_reason,
            status=Ticket.Status.ASSIGNED if assigned_to else serializer.validated_data.get("status", Ticket.Status.NEW),
        )
        for uploaded_file in self.request.FILES.getlist("screenshots"):
            TicketAttachment.objects.create(ticket=ticket, file=uploaded_file, uploaded_by=self.request.user)
        recipients = {ticket.project.owner, ticket.project.created_by, *ticket.project.admins.all(), *User.objects.filter(role=User.Role.SUPER_ADMIN)}
        if ticket.assigned_to:
            recipients.add(ticket.assigned_to)
        for recipient in recipients:
            if recipient and recipient.id != self.request.user.id:
                notify_user(
                    recipient=recipient,
                    sender=self.request.user,
                    title="New ITSM ticket",
                    message=f"{ticket.ticket_id} - {ticket.title} was raised for {ticket.project.name}.",
                    type="WARNING" if ticket.priority in {Ticket.Priority.P1, Ticket.Priority.P2} else "INFO",
                    project=ticket.project,
                )
        from apps.audit.services import audit_event

        audit_event(self.request, "CREATE", "Ticket", ticket.pk, {"ticket_id": ticket.ticket_id, "status": ticket.status, "priority": ticket.priority})

    def perform_update(self, serializer):
        ticket = serializer.save()
        recipients = {ticket.requester, ticket.raised_by, ticket.assigned_to, ticket.project.owner, *ticket.project.admins.all()}
        for recipient in recipients:
            if recipient and recipient.id != self.request.user.id:
                notify_user(
                    recipient=recipient,
                    sender=self.request.user,
                    title="Ticket updated",
                    message=f"{ticket.ticket_id} is now {ticket.get_status_display()}.",
                    project=ticket.project,
                )
        from apps.audit.services import audit_event

        audit_event(self.request, "UPDATE", "Ticket", ticket.pk, {"ticket_id": ticket.ticket_id, "status": ticket.status})

    def destroy(self, request, *args, **kwargs):
        if not is_admin_level(request.user):
            return Response({"detail": "Only Admin and Super Admin can delete tickets."}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)

    @decorators.action(detail=True, methods=["post"])
    def attach(self, request, pk=None):
        ticket = self.get_object()
        created = []
        for uploaded_file in request.FILES.getlist("files"):
            created.append(TicketAttachment.objects.create(ticket=ticket, file=uploaded_file, uploaded_by=request.user))
        record_activity(ticket, "attachment.added", actor=request.user, metadata={"count": len(created)})
        return Response(TicketAttachmentSerializer(created, many=True, context={"request": request}).data, status=status.HTTP_201_CREATED)

    @decorators.action(detail=True, methods=["post"])
    def comment(self, request, pk=None):
        ticket = self.get_object()
        serializer = TicketCommentSerializer(data={**request.data, "ticket": ticket.id}, context={"request": request})
        serializer.is_valid(raise_exception=True)
        comment = serializer.save(author=request.user)
        for uploaded_file in request.FILES.getlist("files"):
            TicketAttachment.objects.create(ticket=ticket, comment=comment, file=uploaded_file, uploaded_by=request.user)
        record_activity(ticket, "comment.added", actor=request.user, metadata={"comment_id": comment.id, "is_internal": comment.is_internal})
        if ticket.requester and ticket.requester_id != request.user.id and not comment.is_internal:
            notify_user(
                recipient=ticket.requester,
                sender=request.user,
                title="Ticket response",
                message=f"A response was added to {ticket.ticket_id}.",
                project=ticket.project,
            )
        return Response(TicketCommentSerializer(comment, context={"request": request}).data, status=status.HTTP_201_CREATED)

    @decorators.action(detail=True, methods=["post"], url_path="create-approval")
    def create_approval(self, request, pk=None):
        if not is_admin_level(request.user):
            return Response({"detail": "Only Admin and Super Admin can create approvals."}, status=status.HTTP_403_FORBIDDEN)
        ticket = self.get_object()
        template_id = request.data.get("template")
        template = ApprovalTemplate.objects.filter(pk=template_id, is_active=True).first()
        if not template:
            return Response({"detail": "Approval template not found."}, status=status.HTTP_404_NOT_FOUND)
        approval = create_approval_request(ticket, template, requested_by=request.user)
        return Response(ApprovalRequestSerializer(approval, context={"request": request}).data, status=status.HTTP_201_CREATED)


class TicketCommentViewSet(AuditModelViewSetMixin, viewsets.ModelViewSet):
    serializer_class = TicketCommentSerializer
    permission_classes = [IsAuthenticated]
    audit_entity = "TicketComment"

    def get_queryset(self):
        tickets = TicketViewSet()
        tickets.request = self.request
        visible_ticket_ids = tickets.get_queryset().values("id")
        qs = TicketComment.objects.select_related("ticket", "author").prefetch_related("mentions", "attachments").filter(ticket_id__in=visible_ticket_ids)
        ticket_id = self.request.query_params.get("ticket")
        if ticket_id:
            qs = qs.filter(ticket_id=ticket_id)
        if has_role(self.request.user, Roles.CLIENT):
            qs = qs.filter(is_internal=False)
        return qs

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


class SLAPolicyViewSet(OrganizationScopedAdminMixin, viewsets.ModelViewSet):
    serializer_class = SLAPolicySerializer

    def get_queryset(self):
        return SLAPolicy.objects.filter(Q(organization=getattr(self.request.user, "company", None)) | Q(organization__isnull=True))


class BusinessHoursViewSet(OrganizationScopedAdminMixin, viewsets.ModelViewSet):
    serializer_class = BusinessHoursSerializer

    def get_queryset(self):
        return BusinessHours.objects.filter(Q(organization=getattr(self.request.user, "company", None)) | Q(organization__isnull=True))


class HolidayViewSet(OrganizationScopedAdminMixin, viewsets.ModelViewSet):
    serializer_class = HolidaySerializer

    def get_queryset(self):
        return Holiday.objects.filter(Q(organization=getattr(self.request.user, "company", None)) | Q(organization__isnull=True))


class ServiceItemViewSet(OrganizationScopedAdminMixin, viewsets.ModelViewSet):
    serializer_class = ServiceItemSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "category"]
    ordering = ["name"]

    def get_queryset(self):
        return ServiceItem.objects.filter(Q(organization=getattr(self.request.user, "company", None)) | Q(organization__isnull=True))


class WorkflowTemplateViewSet(OrganizationScopedAdminMixin, viewsets.ModelViewSet):
    serializer_class = WorkflowTemplateSerializer

    def get_queryset(self):
        return WorkflowTemplate.objects.filter(Q(organization=getattr(self.request.user, "company", None)) | Q(organization__isnull=True))


class WorkflowExecutionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = WorkflowExecutionSerializer
    permission_classes = [IsAuthenticated, IsAdminLevel]

    def get_queryset(self):
        return WorkflowExecution.objects.select_related("template", "ticket").filter(ticket__organization=getattr(self.request.user, "company", None))


class ApprovalTemplateViewSet(OrganizationScopedAdminMixin, viewsets.ModelViewSet):
    serializer_class = ApprovalTemplateSerializer

    def get_queryset(self):
        return ApprovalTemplate.objects.filter(Q(organization=getattr(self.request.user, "company", None)) | Q(organization__isnull=True))


class ApprovalRequestViewSet(viewsets.ModelViewSet):
    serializer_class = ApprovalRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tickets = TicketViewSet()
        tickets.request = self.request
        visible_ticket_ids = tickets.get_queryset().values("id")
        return ApprovalRequest.objects.select_related("ticket", "template", "requested_by").prefetch_related("stages").filter(ticket_id__in=visible_ticket_ids)

    def create(self, request, *args, **kwargs):
        if not is_admin_level(request.user):
            return Response({"detail": "Only Admin and Super Admin can create approvals."}, status=status.HTTP_403_FORBIDDEN)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(requested_by=self.request.user)

    @decorators.action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self._decide(request, ApprovalStage.Status.APPROVED)

    @decorators.action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        return self._decide(request, ApprovalStage.Status.REJECTED)

    def _decide(self, request, decision):
        approval = self.get_object()
        serializer = ApprovalDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        stages = approval.stages.filter(status=ApprovalStage.Status.PENDING)
        if approval.template and not approval.template.is_parallel:
            stages = stages.filter(order=approval.current_stage_order)
        stage = next((item for item in stages if item.can_decide(request.user) or is_admin_level(request.user)), None)
        if not stage:
            return Response({"detail": "No pending approval stage is available for this user."}, status=status.HTTP_403_FORBIDDEN)
        stage.status = decision
        stage.comments = serializer.validated_data.get("comments", "")
        stage.decided_by = request.user
        stage.decided_at = timezone.now()
        stage.save(update_fields=["status", "comments", "decided_by", "decided_at", "updated_at"])
        if approval.template and not approval.template.is_parallel and decision == ApprovalStage.Status.APPROVED:
            next_stage = approval.stages.filter(status=ApprovalStage.Status.PENDING).order_by("order").first()
            if next_stage:
                approval.current_stage_order = next_stage.order
                approval.save(update_fields=["current_stage_order", "updated_at"])
        approval.refresh_status()
        record_activity(approval.ticket, f"approval.{decision.lower()}", actor=request.user, metadata={"approval_id": approval.id, "stage": stage.name})
        return Response(ApprovalRequestSerializer(approval, context={"request": request}).data)


class ApprovalStageViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ApprovalStageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        approvals = ApprovalRequestViewSet()
        approvals.request = self.request
        visible_ids = approvals.get_queryset().values("id")
        return ApprovalStage.objects.select_related("approval_request", "approver", "decided_by").filter(approval_request_id__in=visible_ids)
