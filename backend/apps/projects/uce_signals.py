from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.projects.models import UCEMilestone, UCEProject, UCETask, UCETimeEntry
from apps.webhooks.services import emit_event


@receiver(post_save, sender=UCEProject)
@receiver(post_save, sender=UCEMilestone)
@receiver(post_save, sender=UCETask)
@receiver(post_save, sender=UCETimeEntry)
def emit_projects_event(sender, instance, created, **kwargs):
    emit_event("created" if created else "updated", "projects", sender.__name__, str(instance.pk), {"repr": str(instance)})

