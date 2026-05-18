from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.crm.models import Activity, Company, Contact, Deal
from apps.webhooks.services import emit_event


@receiver(post_save, sender=Company)
@receiver(post_save, sender=Contact)
@receiver(post_save, sender=Deal)
@receiver(post_save, sender=Activity)
def emit_crm_event(sender, instance, created, **kwargs):
    emit_event("created" if created else "updated", "crm", sender.__name__, str(instance.pk), {"repr": str(instance)})

