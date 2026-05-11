from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.dispatch import Signal, receiver
from django.db.models.signals import post_save, pre_save

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
        run_workflows(instance, "STATUS_CHANGED")
    ticket_updated.send(sender=Ticket, ticket=instance)
    broadcast_ticket(instance, "ticket.updated")


@receiver(escalate_ticket)
def handle_escalation(sender, ticket, **kwargs):
    record_activity(ticket, "sla.breached", metadata={"sla_due_at": ticket.sla_due_at.isoformat() if ticket.sla_due_at else None})
    run_workflows(ticket, "SLA_BREACHED")
    broadcast_ticket(ticket, "ticket.sla_breached")
