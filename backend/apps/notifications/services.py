from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import Notification
from .serializers import NotificationSerializer


def broadcast_notification(notification):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    async_to_sync(channel_layer.group_send)(
        f"notifications_{notification.recipient_id}",
        {
            "type": "new.notification",
            "data": NotificationSerializer(notification).data,
        },
    )


def notify_user(recipient, title, message, sender=None, type="INFO", urgency="info", project=None, task=None, hosted_project=None, server=None):
    notification = Notification.objects.create(
        recipient=recipient,
        sender=sender,
        title=title,
        message=message,
        type=type,
        urgency=urgency,
        project=project,
        task=task,
        hosted_project=hosted_project,
        server=server,
    )
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
