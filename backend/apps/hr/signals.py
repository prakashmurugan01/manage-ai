from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.hr.models import Department, Employee, LeaveRequest, Payroll
from apps.webhooks.services import emit_event


@receiver(post_save, sender=Department)
@receiver(post_save, sender=Employee)
@receiver(post_save, sender=LeaveRequest)
@receiver(post_save, sender=Payroll)
def emit_hr_event(sender, instance, created, **kwargs):
    emit_event("created" if created else "updated", "hr", sender.__name__, str(instance.pk), {"repr": str(instance)})

