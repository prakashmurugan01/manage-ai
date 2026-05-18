from django.conf import settings
from django.db import models

from apps.core.models import UCEModel


class Department(UCEModel):
    name = models.CharField(max_length=160, unique=True)
    head = models.ForeignKey("hr.Employee", related_name="headed_departments", on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    budget = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    employee_count = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Employee(UCEModel):
    emp_code = models.CharField(max_length=60, unique=True)
    name = models.CharField(max_length=180, db_index=True)
    email = models.EmailField(unique=True)
    department = models.ForeignKey("hr.Department", related_name="employees", on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    role = models.CharField(max_length=120, db_index=True)
    manager = models.ForeignKey("self", related_name="reports", on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    salary = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    start_date = models.DateField(null=True, blank=True, db_index=True)
    status = models.CharField(max_length=40, default="active", db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="hr_profiles", on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["department", "status"])]

    def __str__(self):
        return self.name


class LeaveRequest(UCEModel):
    employee = models.ForeignKey("hr.Employee", related_name="leave_requests", on_delete=models.CASCADE, db_index=True)
    type = models.CharField(max_length=60, db_index=True)
    start_date = models.DateField(db_index=True)
    end_date = models.DateField(db_index=True)
    status = models.CharField(max_length=40, default="pending", db_index=True)
    approved_by = models.ForeignKey("hr.Employee", related_name="approved_leave_requests", on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.employee} {self.type}"


class Payroll(UCEModel):
    employee = models.ForeignKey("hr.Employee", related_name="payroll_runs", on_delete=models.CASCADE, db_index=True)
    period = models.CharField(max_length=30, db_index=True)
    gross = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    deductions = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    net = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    processed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    payment_status = models.CharField(max_length=40, default="pending", db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-period", "-created_at"]
        constraints = [models.UniqueConstraint(fields=["employee", "period"], name="unique_employee_payroll_period")]

    def __str__(self):
        return f"{self.employee} {self.period}"

