from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone
from celery import shared_task
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from apps.hosting.models import HostedProject

from .models import Notification
from .serializers import NotificationSerializer


@shared_task
def check_hosting_expiry():
    thresholds = [60, 30, 7, 1]
    today = timezone.localdate()
    count = 0
    for project in HostedProject.objects.filter(status="live"):
        user = _notification_user(project)
        if not user:
            continue
        days = (project.expiry_date - today).days
        if days not in thresholds:
            continue
        exists = Notification.objects.filter(hosted_project=project, days_threshold=days, created_at__year=today.year).exists()
        if exists:
            continue
        urgency = "info" if days >= 30 else ("warning" if days >= 7 else "critical")
        notification = Notification.objects.create(
            recipient=user,
            hosted_project=project,
            type=Notification.Type.WARNING if days > 1 else Notification.Type.ALERT,
            urgency=urgency,
            title=f"{project.name} expires in {days} days",
            message=f"{project.domain} has {days} day(s) remaining before expiry.",
            days_threshold=days,
        )
        send_expiry_email.delay(notification.id)
        _broadcast(notification)
        count += 1
    for project in HostedProject.objects.filter(status="live", expiry_date__lt=today):
        user = _notification_user(project)
        project.status = "expired"
        project.save(update_fields=["status"])
        if not user:
            continue
        notification = Notification.objects.create(
            recipient=user,
            hosted_project=project,
            type=Notification.Type.ALERT,
            urgency="critical",
            title=f"EXPIRED: {project.domain}",
            message=f"The hosting for {project.domain} expired on {project.expiry_date}.",
        )
        _broadcast(notification)
        count += 1
    return count


@shared_task
def send_expiry_email(notification_id):
    notification = Notification.objects.select_related("recipient").get(id=notification_id)
    if notification.is_sent_email:
        return True
    prefix = {"info": "[INFO]", "warning": "[WARNING]", "critical": "[CRITICAL]"}.get(notification.urgency, "[INFO]")
    send_mail(
        f"{prefix} {notification.title}",
        notification.message,
        None,
        [notification.recipient.email],
        fail_silently=True,
    )
    notification.is_sent_email = True
    notification.save(update_fields=["is_sent_email"])
    return True


def _notification_user(project):
    client = getattr(project, "client", None)
    user = getattr(client, "account_manager", None) if client else None
    return user or get_user_model().objects.filter(is_active=True).first()


def _broadcast(notification):
    channel_layer = get_channel_layer()
    if channel_layer:
        async_to_sync(channel_layer.group_send)(
            f"notifications_{notification.recipient_id}",
            {"type": "new.notification", "data": NotificationSerializer(notification).data},
        )
