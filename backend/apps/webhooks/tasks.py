from celery import shared_task
from django.utils import timezone


MODULE_PRIORITY = {
    "erp": 90,
    "inventory": 80,
    "crm": 70,
    "projects": 60,
    "hr": 50,
}


def _event_version(event):
    payload = event.payload or {}
    for key in ("version", "revision", "updated_at", "timestamp"):
        value = payload.get(key)
        if value not in (None, ""):
            return str(value)
    return event.updated_at.isoformat()


def _detect_conflict(event, target_module):
    from apps.webhooks.models import Event

    if not event.entity_id:
        return False, {}

    payload = event.payload or {}
    source_version = _event_version(event)
    newer_events = (
        Event.objects.filter(
            entity_id=event.entity_id,
            source_module=target_module,
            is_deleted=False,
        )
        .exclude(id=event.id)
        .order_by("-updated_at")[:5]
    )
    competing = []
    for candidate in newer_events:
        candidate_version = _event_version(candidate)
        if candidate.updated_at >= event.updated_at or candidate_version != source_version:
            competing.append({
                "event_id": str(candidate.id),
                "event_type": candidate.event_type,
                "version": candidate_version,
                "updated_at": candidate.updated_at.isoformat(),
            })

    forced = bool(payload.get("force_conflict") or payload.get("conflict"))
    conflict_detected = forced or bool(competing)
    metadata = {
        "source_version": source_version,
        "competing_events": competing,
        "source_priority": MODULE_PRIORITY.get(event.source_module, 10),
        "target_priority": MODULE_PRIORITY.get(target_module, 10),
    }
    return conflict_detected, metadata


def _resolution_strategy(event, target_module, conflict_detected):
    from apps.webhooks.models import DataSyncLog

    if not conflict_detected:
        return DataSyncLog.ResolutionStrategy.TIMESTAMP
    source_priority = MODULE_PRIORITY.get(event.source_module, 10)
    target_priority = MODULE_PRIORITY.get(target_module, 10)
    if source_priority != target_priority:
        return DataSyncLog.ResolutionStrategy.PRIORITY
    return DataSyncLog.ResolutionStrategy.MANUAL


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
        conflict_detected, conflict_metadata = _detect_conflict(event, target_module)
        resolution_strategy = _resolution_strategy(event, target_module, conflict_detected)
        resolved_at = None if resolution_strategy == DataSyncLog.ResolutionStrategy.MANUAL else timezone.now()
        DataSyncLog.objects.create(
            source_module=event.source_module,
            target_module=target_module,
            entity_id=event.entity_id,
            conflict_detected=conflict_detected,
            resolution_strategy=resolution_strategy,
            resolved_at=resolved_at,
            metadata={
                "event_id": str(event.id),
                "event_type": event.event_type,
                **conflict_metadata,
            },
        )
    event.processed_at = timezone.now()
    event.save(update_fields=["processed_at", "updated_at"])
    return {"processed": True, "dependent_modules": dependent_modules}
