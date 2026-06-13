from celery import shared_task

from .services import mark_stale_agents


@shared_task
def mark_stale_project_agents():
    return mark_stale_agents()
