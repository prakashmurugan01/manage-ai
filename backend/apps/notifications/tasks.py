from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db.models import Q
from django.utils import timezone
from celery import shared_task
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from apps.hosting.models import HostedProject

from .models import Notification
from .serializers import NotificationSerializer


@shared_task
def check_hosting_expiry():
    thresholds = [60, 30, 14, 7, 1]
    today = timezone.localdate()
    count = 0
    for project in HostedProject.objects.select_related("client").filter(status=HostedProject.Status.LIVE):
        user = _notification_user(project)
        if not user:
            continue
        days = (project.expiry_date - today).days
        if days not in thresholds:
            continue
        exists = Notification.objects.filter(
            hosted_project=project,
            days_threshold=days,
            type=Notification.Type.EXPIRY_WARNING,
            created_at__year=today.year,
        ).exists()
        if exists:
            continue
        urgency = "info" if days >= 30 else ("warning" if days >= 7 else "critical")
        notification = Notification.objects.create(
            recipient=user,
            hosted_project=project,
            type=Notification.Type.EXPIRY_WARNING,
            urgency=urgency,
            title=f"Hosting expiry in {days} days: {project.name}",
            message=f"The hosting for {project.domain} expires on {project.expiry_date}. Please renew to avoid downtime.",
            days_threshold=days,
        )
        send_expiry_email.delay(notification.id)
        count += 1
    for project in HostedProject.objects.select_related("client").filter(status=HostedProject.Status.LIVE, expiry_date__lt=today):
        user = _notification_user(project)
        project.status = HostedProject.Status.EXPIRED
        project.save(update_fields=["status"])
        if not user:
            continue
        exists = Notification.objects.filter(
            hosted_project=project,
            type=Notification.Type.EXPIRY_WARNING,
            urgency=Notification.Urgency.CRITICAL,
            title__startswith=f"EXPIRED: {project.domain}",
            created_at__year=today.year,
        ).exists()
        if exists:
            continue
        notification = Notification.objects.create(
            recipient=user,
            hosted_project=project,
            type=Notification.Type.EXPIRY_WARNING,
            urgency=Notification.Urgency.CRITICAL,
            title=f"EXPIRED: {project.domain}",
            message=f"The hosting for {project.domain} expired on {project.expiry_date}. Restore or renew immediately to avoid continued downtime.",
        )
        send_expiry_email.delay(notification.id)
        count += 1
    return count


@shared_task
def send_expiry_email(notification_id):
    notification = Notification.objects.select_related("recipient", "hosted_project", "server").get(id=notification_id)
    if notification.is_sent_email:
        return True
    if not notification.recipient.email:
        return False
    prefix = {
        Notification.Urgency.INFO: "[INFO]",
        Notification.Urgency.WARNING: "[WARNING]",
        Notification.Urgency.CRITICAL: "[CRITICAL]",
    }.get(notification.urgency, "[INFO]")
    if notification.urgency == Notification.Urgency.CRITICAL and notification.type == Notification.Type.EXPIRY_WARNING:
        prefix = "[URGENT]"
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
    if user:
        return user
    User = get_user_model()
    return (
        User.objects.filter(
            Q(role__in=["SUPER_ADMIN", "ADMIN"]) | Q(is_superuser=True),
            is_active=True,
        )
        .order_by("-is_superuser", "id")
        .first()
        or User.objects.filter(is_active=True).order_by("id").first()
    )


def _broadcast(notification):
    channel_layer = get_channel_layer()
    if channel_layer:
        async_to_sync(channel_layer.group_send)(
            f"notifications_{notification.recipient_id}",
            {
                "type": "new.notification",
                "data": NotificationSerializer(notification).data,
            },
        )
