from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import EmailEvent


def send_automation_email(recipient, subject, body, company=None):
    event = EmailEvent.objects.create(company=company, recipient=recipient, subject=subject, body=body)
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@manageai.local"),
            recipient_list=[recipient],
            fail_silently=False,
        )
    except Exception as exc:
        event.status = EmailEvent.Status.FAILED
        event.error = str(exc)[:1000]
        event.save(update_fields=["status", "error", "updated_at"])
        return event

    event.status = EmailEvent.Status.SENT
    event.sent_at = timezone.now()
    event.save(update_fields=["status", "sent_at", "updated_at"])
    return event
