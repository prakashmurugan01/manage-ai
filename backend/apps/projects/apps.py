from django.apps import AppConfig


class ProjectsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.projects"
    module_id = "projects"
    display_name = "Project Management"
    version = "1.0.0"
    supported_query_types = ["rest", "nl"]
    schema = {
        "UCEProject": {"client": "uuid", "status": "string", "budget": "decimal", "deadline": "date"},
        "UCEMilestone": {"project": "uuid", "title": "string", "due_date": "date"},
        "UCETask": {"project": "uuid", "assigned_to": "uuid", "status": "string"},
        "UCETimeEntry": {"task": "uuid", "employee": "uuid", "hours": "decimal"},
    }
    endpoints = ["/api/v1/projects/", "/api/v1/projects/tasks/", "/api/v1/projects/time-entries/"]

    def ready(self):
        from apps.projects import uce_signals  # noqa: F401
