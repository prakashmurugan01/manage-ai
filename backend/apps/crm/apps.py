from django.apps import AppConfig


class CrmConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.crm"
    label = "crm"
    module_id = "crm"
    display_name = "CRM"
    version = "1.0.0"
    supported_query_types = ["rest", "nl"]
    schema = {
        "Contact": {"name": "string", "email": "email", "company": "uuid", "lifecycle_stage": "string"},
        "Company": {"name": "string", "industry": "string", "annual_revenue": "decimal", "status": "string"},
        "Deal": {"title": "string", "company": "uuid", "value": "decimal", "stage": "string"},
        "Activity": {"type": "string", "contact": "uuid", "deal": "uuid", "activity_date": "datetime"},
    }
    endpoints = ["/api/v1/crm/contacts/", "/api/v1/crm/companies/", "/api/v1/crm/deals/", "/api/v1/crm/activities/"]

    def ready(self):
        from apps.crm import signals  # noqa: F401

