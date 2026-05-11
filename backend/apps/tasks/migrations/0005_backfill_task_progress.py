from django.db import migrations


def backfill_task_progress(apps, schema_editor):
    Task = apps.get_model("tasks", "Task")
    Project = apps.get_model("projects", "Project")
    Task.objects.filter(status="DONE", progress_percent=0).update(progress_percent=100)
    for project in Project.objects.all():
        tasks = Task.objects.filter(project_id=project.id)
        total = tasks.count()
        if total:
            project.progress = round(sum(task.progress_percent for task in tasks) / total)
            project.save(update_fields=["progress", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("tasks", "0004_task_progress_percent"),
    ]

    operations = [
        migrations.RunPython(backfill_task_progress, migrations.RunPython.noop),
    ]
