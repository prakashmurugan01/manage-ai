from celery import shared_task
from django.utils import timezone


@shared_task(name="uce.process_cross_module_event")
def process_cross_module_event(event_id):
    from apps.webhooks.models import DataSyncLog, Event

    event = Event.objects.filter(id=event_id, is_deleted=False).first()
    if not event:
        return {"processed": False, "reason": "event_not_found"}
    dependent_modules = {
        "crm": ["erp", "projects"],
        "erp": ["crm", "projects"],
        "hr": ["projects"],
        "inventory": ["projects", "erp"],
        "projects": ["crm", "hr", "erp"],
    }.get(event.source_module, [])
    for target_module in dependent_modules:
        DataSyncLog.objects.create(
            source_module=event.source_module,
            target_module=target_module,
            entity_id=event.entity_id,
            conflict_detected=False,
            resolution_strategy=DataSyncLog.ResolutionStrategy.TIMESTAMP,
            resolved_at=timezone.now(),
            metadata={"event_id": str(event.id), "event_type": event.event_type},
        )
    event.processed_at = timezone.now()
    event.save(update_fields=["processed_at", "updated_at"])
    return {"processed": True, "dependent_modules": dependent_modules}

