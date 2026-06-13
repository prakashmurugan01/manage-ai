from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.dispatch import Signal, receiver
from django.db.models.signals import post_save, pre_save

from apps.notifications.services import notify_user

from .models import Ticket
from .services import apply_sla, record_activity, run_workflows


ticket_updated = Signal()
ticket_created = Signal()
escalate_ticket = Signal()


def _ticket_payload(ticket):
    return {
        "id": ticket.id,
        "ticket_id": ticket.ticket_id,
        "title": ticket.title,
        "status": ticket.status,
        "priority": ticket.priority,
        "assigned_to": ticket.assigned_to_id,
        "sla_due_at": ticket.sla_due_at.isoformat() if ticket.sla_due_at else None,
        "sla_breached": ticket.sla_breached,
        "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
    }


def broadcast_ticket(ticket, event_type):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    payload = _ticket_payload(ticket)
    groups = {f"ticket_{ticket.id}"}
    if ticket.organization_id:
        groups.add(f"ticket_list_{ticket.organization_id}")
    for group in groups:
        try:
            async_to_sync(channel_layer.group_send)(
                group,
                {"type": "ticket.event", "event": event_type, "ticket": payload},
            )
        except Exception:
            pass


@receiver(pre_save, sender=Ticket)
def capture_ticket_changes(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_values = {}
        return
    try:
        previous = Ticket.objects.get(pk=instance.pk)
    except Ticket.DoesNotExist:
        instance._previous_values = {}
        return
    instance._previous_values = {
        "status": previous.status,
        "priority": previous.priority,
        "assigned_to_id": previous.assigned_to_id,
        "sla_breached": previous.sla_breached,
    }


@receiver(post_save, sender=Ticket)
def handle_ticket_saved(sender, instance, created, **kwargs):
    if created:
        apply_sla(instance)
        record_activity(instance, "ticket.created", actor=instance.requester or instance.raised_by)
        _notify_ticket_created(instance)
        ticket_created.send(sender=Ticket, ticket=instance)
        run_workflows(instance, "TICKET_CREATED", actor=instance.requester or instance.raised_by)
        broadcast_ticket(instance, "ticket.created")
        return

    previous = getattr(instance, "_previous_values", {})
    for field in ("status", "priority", "assigned_to_id"):
        if previous.get(field) != getattr(instance, field):
            record_activity(
                instance,
                "ticket.updated",
                field_changed=field,
                old_value=previous.get(field),
                new_value=getattr(instance, field),
            )
    if previous.get("status") != instance.status:
        if instance.status == Ticket.Status.RESOLVED:
            _notify_ticket_resolved(instance)
        run_workflows(instance, "STATUS_CHANGED")
    if previous.get("assigned_to_id") != instance.assigned_to_id and instance.assigned_to_id:
        _notify_ticket_assigned(instance)
    ticket_updated.send(sender=Ticket, ticket=instance)
    broadcast_ticket(instance, "ticket.updated")


@receiver(escalate_ticket)
def handle_escalation(sender, ticket, **kwargs):
    record_activity(ticket, "sla.breached", metadata={"sla_due_at": ticket.sla_due_at.isoformat() if ticket.sla_due_at else None})
    run_workflows(ticket, "SLA_BREACHED")
    broadcast_ticket(ticket, "ticket.sla_breached")


def _notify_ticket_created(ticket):
    recipients = _project_admin_recipients(ticket)
    for recipient in recipients:
        _safe_notify(
            recipient,
            title=f"New ticket: {ticket.title}",
            message=f"{ticket.ticket_id} was created for {ticket.project.name}. Priority: {ticket.priority}.",
            type="ALERT" if ticket.priority in {"P1", "CRITICAL"} else "INFO",
            urgency="critical" if ticket.priority in {"P1", "CRITICAL"} else "info",
            project=ticket.project,
        )


def _notify_ticket_assigned(ticket):
    _safe_notify(
        ticket.assigned_to,
        title=f"Ticket assigned: {ticket.ticket_id}",
        message=f"You have been assigned '{ticket.title}' for {ticket.project.name}.",
        type="INFO",
        urgency="warning" if ticket.priority in {"P1", "P2", "CRITICAL", "HIGH"} else "info",
        project=ticket.project,
    )


def _notify_ticket_resolved(ticket):
    message = f"{ticket.ticket_id} has been resolved."
    if ticket.resolution_notes:
        message = f"{message}\n\nResolution notes: {ticket.resolution_notes}"
    recipients = {ticket.requester_id: ticket.requester, ticket.raised_by_id: ticket.raised_by, ticket.project.owner_id: ticket.project.owner}
    for recipient in [user for user in recipients.values() if user]:
        _safe_notify(
            recipient,
            title=f"Ticket resolved: {ticket.ticket_id}",
            message=message,
            type="SUCCESS",
            urgency="info",
            project=ticket.project,
        )


def _project_admin_recipients(ticket):
    recipients = []
    if ticket.project.owner_id:
        recipients.append(ticket.project.owner)
    recipients.extend(list(ticket.project.admins.all()))
    seen = set()
    unique = []
    for recipient in recipients:
        if recipient and recipient.id not in seen:
            seen.add(recipient.id)
            unique.append(recipient)
    return unique


def _safe_notify(recipient, **kwargs):
    if not recipient:
        return
    try:
        notify_user(recipient=recipient, **kwargs)
    except Exception:
        pass
