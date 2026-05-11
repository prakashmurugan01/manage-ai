from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import Notification


def notify_user(recipient, title, message, sender=None, type="INFO", project=None, task=None):
    notification = Notification.objects.create(
        recipient=recipient,
        sender=sender,
        title=title,
        message=message,
        type=type,
        project=project,
        task=task,
    )
    channel_layer = get_channel_layer()
    if channel_layer:
        try:
            async_to_sync(channel_layer.group_send)(
                f"user_{recipient.id}",
                {
                    "type": "notification.created",
                    "notification": {
                        "id": notification.id,
                        "title": notification.title,
                        "message": notification.message,
                        "created_at": notification.created_at.isoformat(),
                    },
                },
            )
        except Exception:
            pass
    if getattr(recipient, "email", None):
        try:
            from apps.enterprise.services import send_automation_email

            send_automation_email(
                recipient=recipient.email,
                subject=title,
                body=message,
                company=getattr(project, "company", None) if project else getattr(recipient, "company", None),
            )
        except Exception:
            pass
    return notification
