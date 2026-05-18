from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.erp.models import FinancialAccount, Invoice, JournalEntry, PurchaseOrder
from apps.webhooks.services import emit_event


@receiver(post_save, sender=Invoice)
@receiver(post_save, sender=PurchaseOrder)
@receiver(post_save, sender=FinancialAccount)
@receiver(post_save, sender=JournalEntry)
def emit_erp_event(sender, instance, created, **kwargs):
    emit_event("created" if created else "updated", "erp", sender.__name__, str(instance.pk), {"repr": str(instance)})

