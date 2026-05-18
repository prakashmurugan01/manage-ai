from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.file_tracking.models import DiskVolume, FileAlert, FileEvent, FileTransfer, TrackingRule
from apps.webhooks.services import emit_event


@receiver(post_save, sender=DiskVolume)
@receiver(post_save, sender=FileTransfer)
@receiver(post_save, sender=FileEvent)
@receiver(post_save, sender=FileAlert)
@receiver(post_save, sender=TrackingRule)
def emit_file_tracking_event(sender, instance, created, **kwargs):
    emit_event("created" if created else "updated", "file_tracking", sender.__name__, str(instance.pk), {"repr": str(instance)})

