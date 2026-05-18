from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def emit_event(event_type, source_module, entity_type, entity_id, payload):
    from apps.webhooks.models import Event

    event = Event.objects.create(
        event_type=event_type,
        source_module=source_module,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload,
    )
    broadcast_event(event)
    try:
        from apps.webhooks.tasks import process_cross_module_event

        process_cross_module_event.delay(str(event.id))
    except Exception:
        pass
    return event


def broadcast_event(event):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    async_to_sync(channel_layer.group_send)(
        "uce_events",
        {
            "type": "uce.event",
            "event": {
                "id": str(event.id),
                "event_type": event.event_type,
                "source_module": event.source_module,
                "entity_type": event.entity_type,
                "entity_id": event.entity_id,
                "payload": event.payload,
                "created_at": event.created_at.isoformat(),
            },
        },
    )

