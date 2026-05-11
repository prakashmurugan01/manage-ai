from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.notifications.services import notify_user

from .models import (
    ApprovalRequest,
    ApprovalStage,
    BusinessHours,
    Holiday,
    SLAPolicy,
    Ticket,
    TicketActivity,
    TicketComment,
    WorkflowExecution,
    WorkflowTemplate,
)


def _as_local(value, tz_name):
    tz = ZoneInfo(tz_name or "UTC")
    return timezone.localtime(value, tz)


def _is_holiday(organization, day):
    return Holiday.objects.filter(organization=organization, date=day).exists()


def _business_windows(organization, day):
    rows = BusinessHours.objects.filter(organization=organization, day_of_week=day.weekday()).order_by("start_time")
    if rows.exists():
        return list(rows)
    return [
        type(
            "DefaultBusinessWindow",
            (),
            {"start_time": time(9, 0), "end_time": time(17, 0), "timezone": "UTC"},
        )()
    ]


def compute_due_date(ticket, policy):
    if not policy:
        return None
    duration = policy.resolution_time
    if not policy.business_hours_only:
        return timezone.now() + duration

    remaining = duration
    cursor = timezone.now()
    organization = ticket.organization
    guard = 0
    while remaining.total_seconds() > 0 and guard < 366:
        guard += 1
        local_cursor = _as_local(cursor, "UTC")
        current_day = local_cursor.date()
        if _is_holiday(organization, current_day):
            cursor = datetime.combine(current_day + timedelta(days=1), time.min, tzinfo=ZoneInfo("UTC"))
            continue

        consumed_today = False
        for window in _business_windows(organization, current_day):
            local_tz = ZoneInfo(window.timezone or "UTC")
            window_start = timezone.make_aware(datetime.combine(current_day, window.start_time), local_tz)
            window_end = timezone.make_aware(datetime.combine(current_day, window.end_time), local_tz)
            start = max(cursor, window_start.astimezone(ZoneInfo("UTC")))
            end = window_end.astimezone(ZoneInfo("UTC"))
            if start >= end:
                continue
            available = end - start
            consumed_today = True
            if available >= remaining:
                return start + remaining
            remaining -= available
            cursor = end
        if not consumed_today or remaining.total_seconds() > 0:
            cursor = datetime.combine(current_day + timedelta(days=1), time.min, tzinfo=ZoneInfo("UTC"))
    raise serializers.ValidationError("Unable to compute SLA due date within one year of business hours.")


def apply_sla(ticket):
    policy = (
        SLAPolicy.objects.filter(organization=ticket.organization, priority=ticket.priority, is_active=True)
        .order_by("resolution_time")
        .first()
    )
    if not policy:
        policy = SLAPolicy.objects.filter(organization__isnull=True, priority=ticket.priority, is_active=True).first()
    due_at = compute_due_date(ticket, policy)
    if due_at:
        Ticket.objects.filter(pk=ticket.pk).update(sla_due_at=due_at, updated_at=timezone.now())
        ticket.sla_due_at = due_at
    return due_at


def record_activity(ticket, action, actor=None, field_changed="", old_value="", new_value="", metadata=None):
    return TicketActivity.objects.create(
        ticket=ticket,
        action=action,
        actor=actor,
        field_changed=field_changed,
        old_value="" if old_value is None else str(old_value),
        new_value="" if new_value is None else str(new_value),
        metadata=metadata or {},
    )


class WorkflowService:
    def conditions_match(self, ticket, template):
        conditions = template.trigger_conditions or {}
        for key, expected in conditions.items():
            actual = getattr(ticket, key, None)
            if actual != expected:
                return False
        return True

    @transaction.atomic
    def execute(self, ticket, template, actor=None):
        if not self.conditions_match(ticket, template):
            return None
        execution = WorkflowExecution.objects.create(template=template, ticket=ticket, status=WorkflowExecution.Status.RUNNING, started_at=timezone.now())
        logs = []
        try:
            for index, action in enumerate(template.actions or [], start=1):
                action_type = action.get("type")
                handler = getattr(self, f"action_{action_type}", None)
                if not handler:
                    raise serializers.ValidationError(f"Unsupported workflow action: {action_type}")
                result = handler(ticket, action, actor=actor)
                logs.append({"step": index, "type": action_type, "result": result})
            execution.status = WorkflowExecution.Status.SUCCESS
            execution.completed_at = timezone.now()
            execution.logs = logs
            execution.save(update_fields=["status", "completed_at", "logs", "updated_at"])
            return execution
        except Exception as exc:
            execution.status = WorkflowExecution.Status.FAILED
            execution.error = str(exc)
            execution.logs = logs
            execution.completed_at = timezone.now()
            execution.save(update_fields=["status", "error", "logs", "completed_at", "updated_at"])
            raise

    def action_assign_ticket(self, ticket, action, actor=None):
        user_id = action.get("user_id")
        group_id = action.get("group_id")
        update_fields = ["updated_at"]
        if user_id:
            ticket.assigned_to_id = user_id
            ticket.status = Ticket.Status.ASSIGNED
            update_fields += ["assigned_to", "status"]
        if group_id:
            ticket.assigned_group_id = group_id
            update_fields.append("assigned_group")
        ticket.save(update_fields=update_fields)
        record_activity(ticket, "workflow.assign_ticket", actor=actor, metadata=action)
        return {"assigned_to": ticket.assigned_to_id, "assigned_group": ticket.assigned_group_id}

    def action_change_status(self, ticket, action, actor=None):
        old_status = ticket.status
        ticket.status = action.get("status", ticket.status)
        ticket.save(update_fields=["status", "resolved_at", "closed_at", "updated_at"])
        record_activity(ticket, "workflow.change_status", actor=actor, field_changed="status", old_value=old_status, new_value=ticket.status)
        return {"status": ticket.status}

    def action_send_notification(self, ticket, action, actor=None):
        recipients = {ticket.requester, ticket.raised_by, ticket.assigned_to}
        title = action.get("title") or f"Ticket update: {ticket.ticket_id}"
        message = action.get("message") or ticket.title
        sent = 0
        for recipient in recipients:
            if recipient:
                notify_user(recipient=recipient, sender=actor, title=title, message=message, project=ticket.project)
                sent += 1
        return {"sent": sent}

    def action_add_comment(self, ticket, action, actor=None):
        if not actor:
            raise serializers.ValidationError("add_comment workflow action requires an actor.")
        comment = TicketComment.objects.create(ticket=ticket, author=actor, body=action.get("body", ""), is_internal=bool(action.get("is_internal", True)))
        return {"comment_id": comment.id}

    def action_create_child_ticket(self, ticket, action, actor=None):
        child = Ticket.objects.create(
            project=ticket.project,
            organization=ticket.organization,
            parent_ticket=ticket,
            requester=ticket.requester,
            raised_by=actor or ticket.raised_by,
            type=action.get("ticket_type", Ticket.Type.TASK),
            title=action.get("title", f"Child task for {ticket.ticket_id}"),
            description=action.get("description", ticket.description),
            priority=action.get("priority", ticket.priority),
            category=ticket.category,
            subcategory=ticket.subcategory,
        )
        return {"ticket_id": child.ticket_id}

    def action_trigger_webhook(self, ticket, action, actor=None):
        record_activity(ticket, "workflow.trigger_webhook", actor=actor, metadata={"url": action.get("url"), "deferred": True})
        return {"queued": True}

    def action_ai_classify(self, ticket, action, actor=None):
        fields = ticket.custom_fields or {}
        fields["ai_classification_requested"] = True
        fields["ai_classification_context"] = action.get("context", "")
        ticket.custom_fields = fields
        ticket.save(update_fields=["custom_fields", "updated_at"])
        return {"queued": True}


def run_workflows(ticket, trigger_type, actor=None):
    qs = WorkflowTemplate.objects.filter(is_active=True, trigger_type=trigger_type).filter(
        organization=ticket.organization
    )
    service = WorkflowService()
    executions = []
    for template in qs:
        execution = service.execute(ticket, template, actor=actor)
        if execution:
            executions.append(execution)
    return executions


def create_approval_request(ticket, template, requested_by=None):
    request = ApprovalRequest.objects.create(ticket=ticket, template=template, requested_by=requested_by)
    for index, stage in enumerate(template.stages or [], start=1):
        ApprovalStage.objects.create(
            approval_request=request,
            order=stage.get("order", index),
            name=stage.get("name", f"Stage {index}"),
            approver_id=stage.get("approver_id"),
            approver_role=stage.get("approver_role", ""),
        )
    record_activity(ticket, "approval.created", actor=requested_by, metadata={"template": template.name})
    return request
