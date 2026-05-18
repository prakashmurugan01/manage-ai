from django.apps import AppConfig


class HrConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.hr"
    label = "hr"
    module_id = "hr"
    display_name = "HR"
    version = "1.0.0"
    supported_query_types = ["rest", "nl"]
    schema = {
        "Employee": {"emp_code": "string", "name": "string", "department": "uuid", "salary": "decimal"},
        "Department": {"name": "string", "budget": "decimal"},
        "LeaveRequest": {"employee": "uuid", "type": "string", "status": "string"},
        "Payroll": {"employee": "uuid", "period": "string", "net": "decimal"},
    }
    endpoints = ["/api/v1/hr/employees/", "/api/v1/hr/departments/", "/api/v1/hr/leave-requests/", "/api/v1/hr/payroll/"]

    def ready(self):
        from apps.hr import signals  # noqa: F401

