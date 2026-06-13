from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0004_approvalrequest_approvalstage_approvaltemplate_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="ticket",
            name="resolution_notes",
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name="ticket",
            name="status",
            field=models.CharField(
                choices=[
                    ("NEW", "New"),
                    ("ASSIGNED", "Assigned"),
                    ("IN_PROGRESS", "In Progress"),
                    ("TESTING", "Testing"),
                    ("PENDING", "Pending"),
                    ("RESOLVED", "Resolved"),
                    ("CLOSED", "Closed"),
                    ("OPEN", "Open"),
                    ("TRIAGED", "Triaged"),
                ],
                default="NEW",
                max_length=32,
            ),
        ),
    ]
