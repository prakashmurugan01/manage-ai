from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.inventory.models import InventoryPurchaseOrder, Product, StockLevel, StockMovement
from apps.webhooks.services import emit_event


@receiver(post_save, sender=Product)
@receiver(post_save, sender=StockLevel)
@receiver(post_save, sender=InventoryPurchaseOrder)
@receiver(post_save, sender=StockMovement)
def emit_inventory_event(sender, instance, created, **kwargs):
    emit_event("created" if created else "updated", "inventory", sender.__name__, str(instance.pk), {"repr": str(instance)})

