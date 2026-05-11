import logging

from django.utils import timezone

try:
    from celery import shared_task
except Exception:
    def shared_task(*task_args, **task_kwargs):
        def decorator(func):
            func.delay = func
            return func
        return decorator

from apps.notifications.services import notify_user

from .models import Ticket, WorkflowExecution
from .signals import escalate_ticket
from .services import WorkflowService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def check_sla_breaches(self):
    now = timezone.now()
    breached = Ticket.objects.select_related("project", "requester", "assigned_to").filter(
        sla_due_at__lte=now,
        sla_breached=False,
    ).exclude(status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED])
    count = 0
    for ticket in breached.iterator(chunk_size=200):
        ticket.sla_breached = True
        ticket.save(update_fields=["sla_breached", "updated_at"])
        escalate_ticket.send(sender=Ticket, ticket=ticket)
        recipients = {ticket.requester, ticket.raised_by, ticket.assigned_to, ticket.project.owner, *ticket.project.admins.all()}
        for recipient in recipients:
            if recipient:
                notify_user(
                    recipient=recipient,
                    title=f"SLA breached: {ticket.ticket_id}",
                    message=f"{ticket.title} breached SLA at {ticket.sla_due_at}.",
                    type="ALERT",
                    project=ticket.project,
                )
        count += 1
    logger.info("SLA breach scan completed", extra={"breached": count})
    return {"breached": count}


@shared_task(bind=True, max_retries=3)
def process_workflow_queue(self):
    pending = WorkflowExecution.objects.select_related("ticket", "template").filter(status=WorkflowExecution.Status.PENDING)[:100]
    processed = 0
    service = WorkflowService()
    for execution in pending:
        service.execute(execution.ticket, execution.template)
        processed += 1
    logger.info("Workflow queue processed", extra={"processed": processed})
    return {"processed": processed}


@shared_task(bind=True, max_retries=3)
def close_stale_tickets(self):
    threshold = timezone.now() - timezone.timedelta(days=30)
    qs = Ticket.objects.filter(status=Ticket.Status.RESOLVED, resolved_at__lte=threshold)
    count = qs.update(status=Ticket.Status.CLOSED, closed_at=timezone.now(), updated_at=timezone.now())
    logger.info("Closed stale tickets", extra={"closed": count})
    return {"closed": count}
